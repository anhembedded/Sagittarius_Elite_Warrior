from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from PySide6.QtCore import Signal, Slot
from Sagittarius_Elite_Warrior.src.application.services.indicator_script_registry import (
    IndicatorScriptRegistry,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.list_available_symbols import (
    ListAvailableSymbolsQuery,
)
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.events.market_tick_event import (
    MarketTickEvent,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import Palette
from Sagittarius_Elite_Warrior.src.presentation.ui.common.app_defaults import (
    FALLBACK_INTERVAL,
    FALLBACK_SYMBOL,
    default_interval,
    default_symbol,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.common.health_feed import HealthFeed
from Sagittarius_Elite_Warrior.src.presentation.ui.common.health_status_report import (
    HealthStatusReport,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.theme import (
    BEAR_COLOR,
    BULL_COLOR,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.timeframe_pin_preferences import (
    TimeframePinPreferences,
    find_timeframe_pin_preferences,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.indicator_scripts.runner import (
    IndicatorScriptRunner,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.symbol_picker import (
    SymbolPreferences,
    find_symbol_preferences,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.constants import UIMode
from Sagittarius_Elite_Warrior.src.presentation.ui.state.container_lookup import (
    find_state_coordinator,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.state.state_scope import (
    StateData,
    StateScope,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.state.ui_state_coordinator import (
    UiStateCoordinator,
)
from sagittarius_engine.extensions.pyside_mvc import BasePresenter, safe_ui_action
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken

from .autostart_controller import AutoStartController
from .coordinators.indicator_coordinator import IndicatorCoordinator
from .dashboard_view_model import (
    DATETIME_FORMAT,
    DEFAULT_LOOKBACK_DAYS,
    DashboardQmlViewModel,
)
from .history_pagination_controller import HistoryPaginationController
from .stream_lifecycle_controller import StreamLifecycleController

logger = logging.getLogger("App.Dashboard")

if TYPE_CHECKING:
    from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.dashboard_view import (
        DashboardView,
    )
    from sagittarius_engine.interfaces.i_container import IContainer

# ---------------------------------------------------------------------------
# Constants — no magic values scattered in method bodies
# ---------------------------------------------------------------------------
#: `EPIC-010H` moved the actual defaults into
#: `presentation/ui/common/app_defaults.py`, which reads Settings first and
#: falls back to the same literals these held. Kept as thin aliases so the
#: names existing comments and tests refer to still resolve, and so there is
#: exactly one place left where the value itself is written down.
_DEFAULT_SYMBOLS: tuple[str, ...] = (FALLBACK_SYMBOL,)
_DEFAULT_INTERVAL_STR: str = FALLBACK_INTERVAL

# --- EPIC-010D — remembered form values ------------------------------------
#: This slice's flat keys, named so `capture_state()`/`restore_state()` cannot
#: drift apart.
_SYMBOL_KEY = "symbol"
_INTERVAL_KEY = "interval"
_LOOKBACK_DAYS_KEY = "lookback_days"
#: `EPIC-010G` — the indicator-script checklist. Two keys, not one:
#: remembering only which scripts are ON would let `set_available()`
#: re-apply a `default_enabled` over a script the user deliberately turned
#: off, which is the defect that task exists to close.
_SCRIPTS_ENABLED_KEY = "scripts_enabled"
_SCRIPTS_TOUCHED_KEY = "scripts_touched"

#: Dates are persisted as a DURATION, never as absolute timestamps (design
#: §9.1, risk R2): an absolute window remembered from a month ago would make
#: the next Load History silently fetch an enormous range. Recomputing
#: `now - N days` on restore preserves today's behaviour exactly.
_MAX_LOOKBACK_DAYS = 3650
#: Longest symbol Binance lists is well under this; a generous ceiling that
#: still rejects a corrupted blob is the point, not a precise limit.
_MAX_SYMBOL_LENGTH = 20

_AUTOSTART_ENABLED_CONFIG_KEY: str = "DEV_BOARD_AUTOSTART_ENABLED"
_DEFAULT_AUTOSTART_ENABLED: bool = False

#: How long AutoStartController waits for a real MarketTickEvent before
#: falling back to Load History (see autostart_controller.py). Configurable
#: so integration tests — which take real wall-clock time to run and offer
#: no real WS ticks ever — can push this window far out and get a
#: deterministic run instead of racing a fallback callback that fires mid
#: assertion. Production keeps the 2s default the design was built around.
_AUTOSTART_FALLBACK_SECONDS_CONFIG_KEY: str = "DEV_BOARD_AUTOSTART_FALLBACK_SECONDS"
_DEFAULT_AUTOSTART_FALLBACK_SECONDS: float = 2.0

#: BOT-035 — how many older candles to fetch each time the user scrolls near
#: the left edge of loaded history. User-configurable (IConfig key), but
#: deliberately NOT run through _compute_fetch_limit() — this is a literal
#: "load N more" action, not a warm-up requirement, so it doesn't grow with
#: whatever scripts happen to be enabled.
_LOAD_MORE_BATCH_CANDLES_CONFIG_KEY: str = "CHART_CARD_LOAD_MORE_BATCH_CANDLES"
_DEFAULT_LOAD_MORE_BATCH_CANDLES: int = 75

# WS status badge (top bar) text/color/tone per FSM state — presentational
# only, derived from the state DashboardPresenter already tracks.
#
# `tone` (third element) is `StatusPill.qml`'s semantic vocabulary
# ("idle"|"active"|"success"|"danger" — see that file's own docstring).
# `EPIC-015` Phase 4 added it here, as a third element of the SAME dict,
# rather than a second `UIMode -> tone` switch: the tone for a mode is a
# property of that mode's row, not an independent fact that could drift
# out of sync with its text/colour. Do NOT derive `tone` from `color`
# (a Palette hex string, or `BULL_COLOR`/`BEAR_COLOR`) — that would break
# silently if any of those values ever changed, since a colour string
# carries no semantic meaning `StatusPill.qml` could read back out of it.
_WS_STATUS_BY_MODE = {
    UIMode.IDLE: ("WS: IDLE", Palette.MUTED, "idle"),
    UIMode.LOCKED: ("WS: SYNCING", Palette.ACCENT, "active"),
    UIMode.LIVE: ("WS: LIVE", BULL_COLOR, "success"),
    UIMode.ERROR: ("WS: ERROR", BEAR_COLOR, "danger"),
}


def _is_plausible_symbol(value: object) -> bool:
    """Whether a remembered symbol is worth applying (`EPIC-010D`).

    @details Shape, not membership. The task file's rule reads "only apply if
    it is still in the symbol options the app knows about", which is right for
    a closed dropdown — but this screen's combo is `setEditable(True)` and
    `_DEFAULT_SYMBOLS` holds a single entry, so membership would silently
    discard any symbol the user legitimately typed and hand them "ETHUSDT"
    back on every launch. That defeats the point of remembering it. The
    Database screen (`EPIC-010E`) has a genuinely closed list and gets the
    membership check there instead.
    """
    return (
        isinstance(value, str)
        and value.strip().isalnum()
        and len(value.strip()) <= _MAX_SYMBOL_LENGTH
    )


def _is_known_interval(value: object) -> bool:
    """Whether a remembered interval is still a real `TimeFrame`."""
    if not isinstance(value, str):
        return False
    try:
        TimeFrame(value)
    except ValueError:
        return False
    return True


def _is_key_list(value: object) -> bool:
    """A remembered list of script keys (`EPIC-010G`).

    @details Only shape is checked here — whether a key still names a
    registered script is `restore_selection()`'s job, which intersects
    against the rows that actually exist.
    """
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _is_sane_lookback(value: object) -> bool:
    """@details `isinstance(True, int)` is `True` in Python, so booleans are
    excluded explicitly — `{"lookback_days": true}` in a hand-edited file
    would otherwise be applied as one day."""
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and 1 <= value <= _MAX_LOOKBACK_DAYS
    )


def _tick_to_candle(
    symbol: str,
    interval: str,
    close_timestamp: float,
    open_price: float,
    high_price: float,
    low_price: float,
    close_price: float,
    volume: float,
) -> MarketData:
    """
    @brief Rebuilds a MarketData from the flattened floats a live tick arrives as.
    @details ui_chart_update_signal carries primitives (Qt signals can't ferry a
    domain entity across threads cleanly), but a script's compute() takes the
    whole candle so it can read high/low/volume. Only the OHLCV fields a script
    can actually reach are real; the trade-count/quote-volume fields are filled
    with zeroes because nothing downstream of here reads them — if a script ever
    needs them, widen the signal rather than inventing values.
    @param interval Caller's current `self._active_interval` — this used to be
    the hard-coded `_DEFAULT_INTERVAL_STR` module constant regardless of the
    timeframe actually selected (BOT-034 changed every OTHER read site to the
    instance attribute but missed this one), which mislabeled every live-tick
    candle appended to `_raw_klines_by_symbol` once a user picked a timeframe
    other than "1m" — silently corrupting the cache a later load-more prepend
    rebuild depends on.
    """
    close_time = datetime.fromtimestamp(close_timestamp, tz=UTC)
    return MarketData(
        symbol=symbol,
        interval=interval,
        open_time=close_time,
        open_price=open_price,
        high_price=high_price,
        low_price=low_price,
        close_price=close_price,
        volume=volume,
        close_time=close_time,
        quote_asset_volume=0.0,
        number_of_trades=0,
        taker_buy_base_asset_volume=0.0,
        taker_buy_quote_asset_volume=0.0,
        is_closed=True,
    )


class DashboardPresenter(BasePresenter):
    """
    @brief Não bộ của màn hình Dashboard.

    Nhiệm vụ:
    1. Lắng nghe hành động từ UI (View) → Gọi hệ thống (Engine).
    2. Lắng nghe sự kiện ngầm từ hệ thống (Engine) → Cập nhật UI (View) an toàn.

    Threading contract:
    - All UI mutations go through Qt Signals (thread-safe bridge).
    - Background work is submitted via self._thread_manager.submit(self._method, *args).
    - No inline closures. No per-method container.resolve() calls.

    BOT-030 Phase 4: ChartCard stays a QtWidgets sibling this Presenter talks
    to directly (unchanged); System Controls/Indicators/Monitor moved to QML
    behind a DashboardQmlViewModel, following the same pattern as
    SettingsPresenter/DataManagementPresenter.
    """

    # ------------------------------------------------------------------ #
    # Thread-safe Signal Bridges — worker thread → main UI thread
    #
    # ĐỌC TRƯỚC KHI XOÁ BẤT KỲ SIGNAL NÀO Ở ĐÂY.
    #
    # Đây KHÔNG phải nợ kỹ thuật. Qt queued signal chính là cơ chế Qt thiết kế
    # ra để đưa dữ liệu từ thread nền về main thread. Worker gọi `.emit` của các
    # signal này (được truyền vào controller dưới dạng callback), slot ở main
    # thread mới chạm widget. Xoá chúng = đẩy cập nhật UI sang worker thread,
    # đúng lớp lỗi BUG-031 (QBasicTimer: Timers cannot be started from another
    # thread) — và là kiểu hỏng "app chạy, test xanh, màn hình không cập nhật"
    # mà test offscreen KHÔNG bắt được.
    #
    # `QtEventBridge` (EPIC-008D) KHÔNG thay thế được chúng: nó chỉ bắc cầu cho
    # event đi qua event bus, còn các worker này không bao giờ đụng bus.
    #
    # Signal ở đây hay Event Bus? Hỏi: "màn khác cũng muốn biết chuyện này thì
    # có vô lý không?"
    #   - Vô lý  → sự thật riêng của màn này → giữ Qt signal (chính là đây).
    #   - Hợp lý → sự thật hệ thống → Event Bus + đúng 1 Feed chuẩn hoá
    #              (`presentation/ui/common/`), nhiều màn chỉ *hiển thị*.
    # Thăng cấp lên bus KHI consumer thứ hai xuất hiện thật, không thăng trước.
    #
    # Luật đầy đủ + số liệu đo thật: .agents/rules/architecture-rule.md §6.
    # Lịch sử: EPIC-008G §2 từng đặt chỉ tiêu "xoá 48 signal cầu nối"; đo lại
    # thấy 47/48 là cầu nối thread (không phải cầu nối bus) nên đã dừng.
    # ------------------------------------------------------------------ #
    ui_log_signal = Signal(str)
    ui_chart_update_signal = Signal(str, float, float, float, float, float, float, bool)

    # Dedicated signals for the Auto-Sync Workflow
    ui_history_reloaded_signal = Signal(str, list, list)
    ui_history_load_finished_signal = Signal()
    ui_stream_success_signal = Signal(str)
    ui_stream_failed_signal = Signal(str)

    # BOT-035 — load-more-on-scroll. Separate from ui_history_reloaded_signal/
    # ui_history_load_finished_signal on purpose: "prepend older data" and
    # "replace all data" are different operations on ChartCard (see
    # prepend_historical_data's docstring — it must NOT reset the user's
    # current zoom/pan the way render_historical_data does).
    ui_history_prepended_signal = Signal(str, list, list)
    #: Second arg: whether this fetch actually found any older candles.
    #: HistoryPaginationController's auto-recheck-after-cooldown only arms
    #: when this is True — see its on_load_more_finished docstring for why
    #: (an unconditional recheck loops forever once a symbol's history is
    #: exhausted, since nothing ever moves the "near the edge" boundary).
    ui_history_prepend_finished_signal = Signal(str, bool)

    # EPIC-014 — the exchange's tradable pair list, fetched off the Qt main
    # thread the first time the symbol picker is opened, then delivered back
    # onto it. Mirrors BackTestPresenter's BOT-102 pair exactly; a failure
    # gets its own signal so the log line says what went wrong rather than
    # the picker just staying on "Đang tải".
    _symbolOptionsReadySignal = Signal(list)
    _symbolOptionsFailedSignal = Signal(str)

    # Indicator name -> full (x, y) series computed so far
    ui_indicator_data_signal = Signal(str, list, list)

    # BOT-032 — script key -> its full current set of background-tint spans /
    # status-panel fields. Separate signals from ui_indicator_data_signal
    # because these carry a different shape (per-script, not per-line) and
    # have no built-in-indicator equivalent to share a contract with.
    ui_script_region_signal = Signal(str, list)
    ui_script_info_signal = Signal(str, list)
    ui_script_marker_signal = Signal(str, list)

    INITIAL_STATE = UIMode.IDLE

    def __init__(self, view: DashboardView, container: IContainer) -> None:
        super().__init__(view, container)

        self._view_model = DashboardQmlViewModel()
        # EPIC-010H, middle tier: seed the form from Settings before the view
        # builds its widgets — `DevBoardPanel` reads `view_model.symbol` once
        # while constructing the combo. `restore_state()` later overrides this
        # with a remembered value if there is one, which is the top tier.
        self._view_model.symbol = default_symbol(self.config.get_all(), FALLBACK_SYMBOL)
        view.set_view_model(self._view_model)

        # Resolve IThreadManager exactly once — stored as an instance attribute.
        # No further container.resolve(IThreadManager) calls anywhere else.
        self._thread_manager: IThreadManager = container.resolve(IThreadManager)

        # EPIC-014: `None` means "never fetched", which is what makes the
        # fetch happen once per session rather than on every picker open. An
        # empty list is a real answer (the query returned nothing) and is
        # deliberately NOT retried — a distinction a falsy check would lose.
        self._symbol_options_cache: list[str] | None = None

        # Define allowed FSM transitions
        self.fsm.add_transition(UIMode.IDLE, UIMode.LOCKED)
        self.fsm.add_transition(UIMode.LOCKED, UIMode.LIVE)
        self.fsm.add_transition(UIMode.LOCKED, UIMode.ERROR)
        self.fsm.add_transition(UIMode.ERROR, UIMode.IDLE)
        self.fsm.add_transition(UIMode.LIVE, UIMode.IDLE)
        self.fsm.add_transition(UIMode.LIVE, UIMode.ERROR)

        # Automatically bind FSM state changes to UI Matrix
        self._bind_fsm_to_ui()

        # Top-bar WS status badge — a second, independent global callback
        # (BaseStateMachine supports multiple; see _bind_fsm_to_ui above).
        self.fsm.add_global_callback(self._on_fsm_state_changed_update_ws_badge)

        # Register Lifecycle Hooks for custom behaviors
        self.fsm.on_enter(UIMode.ERROR, self._on_fsm_error)

        self._apply_ws_status_badge(UIMode.IDLE)

        # BOT-034 — cooperative cancellation for background Load History/
        # Start Live work, checked at each step that would otherwise touch a
        # possibly-torn-down chart/view. "Individual tasks should still
        # implement cancellation tokens" is literally what
        # ThreadManagerExtension.shutdown()'s docstring asks for — it calls
        # thread_manager.shutdown(wait=False), so nothing else stops an
        # in-flight background method from continuing to run past app
        # shutdown. Reset on explicit Stop (see _on_stop_stream) so the next
        # Start Live isn't born pre-cancelled — mirrors how
        # BinanceWebsocketService makes a fresh CancellationToken per
        # start_stream() call rather than reusing one for its whole lifetime.
        self._cancellation_token = CancellationToken()
        self._shutdown_requested: bool = False

        self.active_charts: dict = {}

        # BOT-035 — full MarketData objects behind whatever's currently
        # rendered per symbol, kept in chronological order. ChartCard only
        # retains the (t, o, h, l, c) tuple projection it renders from
        # (_raw_history), which is not enough to correctly rebuild+refeed
        # IndicatorScriptRunner after a prepend (scripts need real MarketData,
        # and have no reset() — see history_pagination_controller.py's
        # docstring and BOT-035's task file §2.4). Overwritten (not appended)
        # on every Load History/Start Live, so a stale interval's klines
        # never leak into a later one.
        self._raw_klines_by_symbol: dict[str, list] = {}

        # BOT-035 — one collaborator per Dev Board screen, same lifetime
        # pattern as AutoStartController: constructed once here, torn down
        # implicitly with the presenter (parented to self).
        self._pagination = HistoryPaginationController(
            fetch_older=self._fetch_older_history,
            recheck_edge=self._recheck_edge,
            parent=self,
        )

        # BOT-033 — interval actually used by Load History/Start Live, set by
        # ChartToolbar.sig_timeframe_changed (see _ensure_chart_cards). An
        # instance attribute rather than the module constant so it can change
        # per-run without a restart.
        # EPIC-010H — Settings' DEFAULT_INTERVAL now reaches this screen too.
        # It used to read the module constant only, so editing Settings
        # changed the Backtest screen and silently left this one alone.
        config_values = self.config.get_all()
        self._active_interval: str = default_interval(config_values, FALLBACK_INTERVAL)

        # BOT-033 Phase 2 — symbol actually used by Load History/Start Live,
        # set from DashboardQmlViewModel.symbol at click time (see
        # StreamLifecycleController._on_load_history/_on_start_stream). An
        # instance attribute, same reasoning as _active_interval above: every
        # per-symbol chart-card lookup below (_rebuild_scripts,
        # _on_indicator_data, _on_script_region_data, _on_script_info_data,
        # _on_script_marker_data) must key off whatever symbol is actually
        # loaded, not the _DEFAULT_SYMBOLS[0] constant — otherwise switching
        # to a different symbol silently stops routing indicator data to the
        # (correctly re-keyed) chart card _ensure_chart_cards just built.
        self._active_symbol: str = default_symbol(config_values, FALLBACK_SYMBOL)

        # Custom indicator scripts (BOT-032) are the ONLY indicator mechanism
        # now (Phase 6 — no indicator is hardcoded in the engine; RSI/EMA/MACD
        # ship as default-registered scripts, see binance_bot_module.py).
        # Stored on self (not a local) — BOT-034's _compute_fetch_limit() also
        # needs it, to look up an enabled script's min_warmup_bars.
        self._script_registry: IndicatorScriptRegistry = container.resolve(
            IndicatorScriptRegistry
        )
        self._script_runner = IndicatorScriptRunner(
            registry=self._script_registry,
            emit_line=self.ui_indicator_data_signal.emit,
            emit_region=self.ui_script_region_signal.emit,
            emit_info=self.ui_script_info_signal.emit,
            emit_markers=self.ui_script_marker_signal.emit,
            on_error=self.ui_log_signal.emit,
        )
        # ViewModel owns the enabled/disabled state (Phase 3) — the Presenter
        # only ever hands it what's available, once, same as logModel.
        self._view_model.script_model.set_available(self._script_registry.available())

        # `EPIC-003G` — which chart card a script's data lands on, and how
        # many candles a fetch needs to warm every enabled script up.
        # `get_enabled_script_keys` is a lambda, not the bound method itself,
        # on purpose: `test_dashboard_presenter.py` monkeypatches
        # `presenter._enabled_script_keys` on the instance after
        # construction, and only a late `self._enabled_script_keys()` call
        # sees that — a captured bound method would keep calling the
        # original.
        self._indicator_coordinator = IndicatorCoordinator(
            script_registry=self._script_registry,
            script_runner=self._script_runner,
            config=self.config,
            get_active_charts=lambda: self.active_charts,
            get_active_symbol=lambda: self._active_symbol,
            get_enabled_script_keys=lambda: self._enabled_script_keys(),
        )

        def _get_cancellation_token():
            return self._cancellation_token

        def _reset_cancellation_token():
            self._cancellation_token = CancellationToken()
            return self._cancellation_token

        def _get_active_interval():
            return self._active_interval

        def _set_active_interval(val: str):
            self._active_interval = val

        def _set_active_symbol(val: str):
            self._active_symbol = val

        self._stream_controller = StreamLifecycleController(
            thread_manager=self._thread_manager,
            dispatcher=self.dispatcher,
            config=self.config,
            fsm=self.fsm,
            view_model=self._view_model,
            script_runner=self._script_runner,
            raw_klines_by_symbol=self._raw_klines_by_symbol,
            get_active_interval=_get_active_interval,
            set_active_interval=_set_active_interval,
            set_active_symbol=_set_active_symbol,
            ensure_chart_cards=lambda symbols: self._ensure_chart_cards(symbols),
            rebuild_scripts=lambda: self._rebuild_scripts(),
            compute_fetch_limit=lambda: self._compute_fetch_limit(),
            get_cancellation_token=_get_cancellation_token,
            reset_cancellation_token=_reset_cancellation_token,
            emit_history_reloaded=self.ui_history_reloaded_signal.emit,
            emit_history_load_finished=self.ui_history_load_finished_signal.emit,
            emit_history_prepended=self.ui_history_prepended_signal.emit,
            emit_history_prepend_finished=self.ui_history_prepend_finished_signal.emit,
            emit_stream_success=self.ui_stream_success_signal.emit,
            emit_stream_failed=self.ui_stream_failed_signal.emit,
            emit_log=self.ui_log_signal.emit,
        )

        self._run_load_history = self._stream_controller._run_load_history
        self._run_load_more_history = self._stream_controller._run_load_more_history
        self._run_sync_and_start = self._stream_controller._run_sync_and_start

        # Must be called explicitly at the end of BasePresenter's contract.
        self._connect_ui_signals()
        self._connect_engine_events()
        self._trigger_initial_health_check()

        # EPIC-010D — restore the remembered form values, then start tracking
        # changes. Placed here deliberately: after `_active_interval` and the
        # ViewModel exist for `restore_state()` to write into, and *before*
        # the auto-start block below, which (when config-enabled) calls
        # `_on_start_stream()` immediately and would otherwise stream the
        # default symbol rather than the remembered one.
        #
        # Restoring first and only then connecting `_mark_dirty` keeps the
        # restore from writing the values straight back out as if the user
        # had just typed them.
        self._state_coordinator: UiStateCoordinator | None = find_state_coordinator(
            container
        )
        if self._state_coordinator is not None:
            self._state_coordinator.restore_into(self)
        # EPIC-014 — the shared symbol favourites/recents store, injected
        # into the panel that owns the picker. Optional exactly like the
        # coordinator above: a presenter built against a container that does
        # not know about it keeps an unpersisted store and still works.
        view.set_symbol_preferences(
            find_symbol_preferences(container) or SymbolPreferences()
        )
        # Follow-up to `EPIC-015` Phase 4 — the shared, per-symbol pinned-
        # timeframe store. Optional exactly like the coordinator/symbol
        # store above: set before `_ensure_chart_cards()` is ever invoked
        # (it runs later, off the first market tick/health check, via the
        # `ensure_chart_cards` lambda handed to `StreamLifecycleController`
        # above), so every ChartCard Dev Board builds — now or on a later
        # symbol-list rebuild — is scoped against the same store.
        view.set_timeframe_pin_preferences(
            find_timeframe_pin_preferences(container) or TimeframePinPreferences()
        )

        self._view_model.script_model.enabledKeysChanged.connect(self._mark_state_dirty)
        self._view_model.symbolChanged.connect(self._mark_state_dirty)
        self._view_model.startDateChanged.connect(self._mark_state_dirty)
        self._view_model.endDateChanged.connect(self._mark_state_dirty)

        # EPIC-006D: DevBoardPanel.qml is no longer loaded here — view's
        # set_view_model() now builds the QtWidgets DevBoardPanel directly.
        # .qml file kept on disk, unloaded (EPIC-006's rollback convention).

        # BOT-034 — auto-start Start Live the moment the Dev Board opens,
        # falling back to Load History if no MarketTickEvent proves a real
        # connection within a few seconds. Constructed last: it immediately
        # calls _on_start_stream(), which needs everything above already set
        # up (script runner, signal connections, FSM). Config-gated
        # (default off — BOT-062: opening Dev Board must not silently start
        # a live connection unless the user has opted in); `None` when
        # disabled so `_on_ui_chart_update`'s `self._autostart.on_market_tick()`
        # has to guard against that instead of assuming it always exists.
        self._autostart: AutoStartController | None = None
        is_autostart_enabled = self.config.get(
            _AUTOSTART_ENABLED_CONFIG_KEY,
            _DEFAULT_AUTOSTART_ENABLED,
            cast=bool,
        )
        if is_autostart_enabled:
            fallback_seconds = self.config.get(
                _AUTOSTART_FALLBACK_SECONDS_CONFIG_KEY,
                _DEFAULT_AUTOSTART_FALLBACK_SECONDS,
                cast=float,
            )
            self._autostart = AutoStartController(
                start_stream=self._on_start_stream,
                load_history=self._on_load_history,
                fallback_seconds=fallback_seconds,
                parent=self,
            )
            self._autostart.begin()

    # ================================================================== #
    # Symbol options (EPIC-014) — same shape as BackTestPresenter's BOT-102
    # ================================================================== #

    @Slot()
    @safe_ui_action
    def _on_symbol_picker_open_requested(self) -> None:
        """Fetches the exchange's pair list the first time the picker opens.

        @details Not at screen construction: it is a network round trip, and
        Dev Board is the screen that auto-starts a live stream, so anything
        added to its construction path delays that. A cache hit means a prior
        open already populated the ViewModel and this is a no-op.
        """
        if self._symbol_options_cache is not None:
            return
        self._thread_manager.submit(self._fetch_symbol_options)

    def _fetch_symbol_options(self) -> None:
        """Runs on a worker thread — hence the signals rather than a direct
        ViewModel write, which would touch Qt objects off the main thread."""
        try:
            symbols = self.dispatcher.dispatch(
                ListAvailableSymbolsQuery, ListAvailableSymbolsQuery()
            )
        except Exception as exc:
            logger.exception("Failed to fetch available symbols")
            self._symbolOptionsFailedSignal.emit(str(exc))
            return
        self._symbolOptionsReadySignal.emit(symbols)

    @Slot(list)
    def _on_symbol_options_ready(self, symbols: list[str]) -> None:
        self._symbol_options_cache = symbols
        self._view_model.set_symbol_options(symbols)

    @Slot(str)
    def _on_symbol_options_failed(self, message: str) -> None:
        self._append_log(f"[ERROR] Không tải được danh sách symbol: {message}")

    # ================================================================== #
    # IStateContributor — structural, no base class (EPIC-010D)
    # ================================================================== #

    @property
    def state_scope(self) -> StateScope:
        return StateScope(key="dashboard")

    def capture_state(self) -> StateData:
        script_model = self._view_model.script_model
        return {
            _SYMBOL_KEY: self._view_model.symbol,
            _INTERVAL_KEY: self._active_interval,
            _LOOKBACK_DAYS_KEY: self._current_lookback_days(),
            _SCRIPTS_ENABLED_KEY: list(script_model.enabled_keys),
            _SCRIPTS_TOUCHED_KEY: list(script_model.touched_keys),
        }

    def restore_state(self, data: StateData) -> None:
        """Applies a remembered slice, validating every value on its own.

        @details D5 — a restored value is a request, not a command, and
        boundary rule 4 puts that judgement here rather than in the
        coordinator: the framework does not know what a valid symbol is.
        Each field is validated independently so a symbol that no longer
        parses does not also throw away a perfectly good interval.
        """
        symbol = data.get(_SYMBOL_KEY)
        if _is_plausible_symbol(symbol):
            # The ViewModel, never the widget: `cboSymbol.currentTextChanged`
            # is wired to a handler, and `DevBoardPanel._sync_symbol` applies
            # this to the combo behind a `QSignalBlocker` (mode #12).
            self._view_model.symbol = symbol.strip()

        interval = data.get(_INTERVAL_KEY)
        if _is_known_interval(interval):
            self._active_interval = interval

        lookback_days = data.get(_LOOKBACK_DAYS_KEY)
        if _is_sane_lookback(lookback_days):
            self._apply_lookback_days(lookback_days)

        enabled = data.get(_SCRIPTS_ENABLED_KEY)
        touched = data.get(_SCRIPTS_TOUCHED_KEY)
        if _is_key_list(enabled) and _is_key_list(touched):
            # Both or neither: applying `enabled` without `touched` would
            # leave every key looking untouched, and the next
            # `set_available()` would switch the defaults back on.
            self._view_model.script_model.restore_selection(enabled, touched)

    def _mark_state_dirty(self) -> None:
        if self._state_coordinator is not None:
            self._state_coordinator.mark_dirty(self)

    def _current_lookback_days(self) -> int:
        """The window the form currently describes, as a whole number of days.

        @details Falls back to the module default when the two fields cannot
        be parsed — they are free-text `QLineEdit`s, so a half-typed date is
        an ordinary state to be in, not an error worth surfacing.
        """
        try:
            # DATETIME_FORMAT carries no offset, so both parse naive. Tagged
            # UTC rather than left naive because that is what they actually
            # are — `_apply_lookback_days()` and the ViewModel's own
            # constructor both write them from `datetime.now(UTC)`.
            start = datetime.strptime(
                self._view_model.startDate, DATETIME_FORMAT
            ).replace(tzinfo=UTC)
            end = datetime.strptime(self._view_model.endDate, DATETIME_FORMAT).replace(
                tzinfo=UTC
            )
        except (ValueError, TypeError):
            return DEFAULT_LOOKBACK_DAYS
        days = (end - start).days
        if not 1 <= days <= _MAX_LOOKBACK_DAYS:
            return DEFAULT_LOOKBACK_DAYS
        return days

    def _apply_lookback_days(self, days: int) -> None:
        """Rewrites the date fields as `now - days` .. `now`.

        @details Deliberately recomputed against the current clock rather
        than restored verbatim — that is the whole point of persisting a
        duration (see `_MAX_LOOKBACK_DAYS`' comment).
        """
        now = datetime.now(UTC)
        self._view_model.startDate = (now - timedelta(days=days)).strftime(
            DATETIME_FORMAT
        )
        self._view_model.endDate = now.strftime(DATETIME_FORMAT)

    def shutdown(self) -> None:
        """Cancels owned workers and autostart controller on desktop shutdown."""
        if self._shutdown_requested:
            return
        self._shutdown_requested = True
        if self._cancellation_token is not None:
            self._cancellation_token.cancel()
        if hasattr(self, "_autostart") and self._autostart is not None:
            self._autostart.shutdown()
        if (
            hasattr(self, "_autostart_controller")
            and self._autostart_controller is not None
        ):
            self._autostart_controller.shutdown()

    # ================================================================== #
    # BasePresenter contract implementations
    # ================================================================== #

    def _connect_ui_signals(self) -> None:
        """Kết nối các thao tác bấm nút từ ViewModel vào Presenter."""
        view_model = self._view_model
        view_model.loadHistoryRequested.connect(self._on_load_history)
        view_model.startStreamRequested.connect(self._on_start_stream)
        view_model.stopStreamRequested.connect(self._on_stop_stream)
        view_model.symbolOptionsRequested.connect(self._on_symbol_picker_open_requested)
        self._symbolOptionsReadySignal.connect(self._on_symbol_options_ready)
        self._symbolOptionsFailedSignal.connect(self._on_symbol_options_failed)

        # Internal signals → view model update slots (all execute on the Qt
        # main thread).
        self.ui_log_signal.connect(self._append_log)
        self.ui_chart_update_signal.connect(self._on_ui_chart_update)

        # Signals for Auto-Sync Workflow
        self.ui_history_reloaded_signal.connect(self._on_history_reloaded)
        self.ui_history_load_finished_signal.connect(self._on_history_load_finished)
        self.ui_history_prepended_signal.connect(self._on_history_prepended)
        self.ui_history_prepend_finished_signal.connect(
            self._on_history_prepend_finished
        )
        self.ui_stream_success_signal.connect(self._on_stream_start_success)
        self.ui_stream_failed_signal.connect(self._on_stream_start_failed)
        self.ui_indicator_data_signal.connect(self._on_indicator_data)
        self.ui_script_region_signal.connect(self._on_script_region_data)
        self.ui_script_info_signal.connect(self._on_script_info_data)
        self.ui_script_marker_signal.connect(self._on_script_marker_data)

    def _connect_engine_events(self) -> None:
        """Đăng ký lắng nghe sự kiện từ Engine EventBus."""
        self.event_bus.on(MarketTickEvent, self._handle_market_tick)
        # Sức khoẻ hệ thống là sự thật của HỆ THỐNG, không riêng màn này, nên nó
        # đi qua HealthFeed — một nơi nghe, nhiều màn hiển thị
        # (`architecture-rule.md` §6). Trước đây màn này tự `event_bus.on(...)`
        # rồi tự ghép chuỗi, và Backtest cũng vậy: 2 định dạng khác nhau cho
        # cùng một dữ liệu, bản của Backtest còn mất hẳn `Container`.
        self._health_feed = HealthFeed(self.event_bus, parent=self)
        self._health_feed.healthUpdated.connect(self._on_health_report)

    def _trigger_initial_health_check(self) -> None:
        """Xin số liệu sức khoẻ tươi ngay khi mở màn.

        Trước `EPIC-008G` hàm này resolve `HealthCheckQuery` rồi **tự dựng một
        `HealthUpdatedEvent`** để gọi thẳng handler của chính mình — cách vá cho
        việc `HealthExtension.boot()` chỉ phát đúng một lần lúc `app.boot()`,
        trước khi presenter (lazy) kịp tồn tại. `EPIC-008E` thay bằng cặp
        request/response thật, nên giờ chỉ cần hỏi.
        """
        self._health_feed.request_refresh()

    def _on_health_report(self, report: HealthStatusReport) -> None:
        """Đã ở main thread — `BaseFeed` bọc `QtEventBridge` sẵn."""
        self.ui_log_signal.emit(report.to_log_line())

    # ================================================================== #
    # FSM Hooks
    # ================================================================== #

    def _on_fsm_error(self) -> None:
        """Auto-recover to IDLE immediately after entering the ERROR state."""
        self.fsm.transition_to(UIMode.IDLE)

    def _on_fsm_state_changed_update_ws_badge(self, old_state, new_state) -> None:
        self._apply_ws_status_badge(new_state)

    def _apply_ws_status_badge(self, mode) -> None:
        text, color, tone = _WS_STATUS_BY_MODE.get(
            mode, _WS_STATUS_BY_MODE[UIMode.IDLE]
        )
        self._view_model.set_ws_status(text, color, tone)

    # ================================================================== #
    # UI Helpers
    # ================================================================== #

    @Slot(str)
    def _append_log(self, message: str) -> None:
        self._view_model.log_model.append(message, level="info")

    def _ensure_chart_cards(self, symbols: list[str]) -> list:
        """
        @brief Reuse existing chart cards to prevent history wipeout.
        Only recreates layout if symbols change or no charts exist.
        """
        current_symbols = list(self.active_charts.keys())
        if set(current_symbols) == set(symbols):
            return list(self.active_charts.values())

        chart_cards = self.view.render_symbol_cards(symbols)
        self.active_charts.clear()

        from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
        from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import (
            TimeFrame,
        )

        bar_seconds = TimeFrame(self._active_interval).to_seconds()
        max_candles = self.config.get(
            ConfigKeys.CHART_CARD_MAX_ZOOM_OUT_CANDLES.value, 2000, cast=int
        )

        for card in chart_cards:
            self.active_charts[card.symbol] = card
            card.set_max_visible_x_range(max_candles * bar_seconds)
            # BOT-033 — freshly-created cards only; render_symbol_cards()
            # tears down and rebuilds the old ones on every call, so a
            # connection made here would otherwise accumulate on a widget
            # that no longer exists.
            # EPIC-010D — a fresh ChartToolbar highlights its first button
            # ("1m") regardless of what interval is actually in force, so a
            # restored "5m" would fetch at 5m while the header claimed 1m.
            # Seeded before the connection so this does not re-enter
            # _on_timeframe_changed.
            card.toolbar.set_active(self._active_interval)
            card.toolbar.sig_timeframe_changed.connect(self._on_timeframe_changed)
            # BOT-035 — same reasoning: fresh card, fresh connection.
            card.sig_near_left_edge.connect(self._on_near_left_edge)
        return chart_cards

    # ================================================================== #
    # Custom indicator scripts (BOT-032) — orchestration lives in
    # IndicatorScriptRunner; this presenter only says *when* things happen.
    # ================================================================== #

    def _enabled_script_keys(self) -> list[str]:
        """
        @brief Which scripts to run — read fresh every call, not cached.
        @details Backed by the view model's IndicatorScriptListModel
        (DevBoardPanel.qml's "CUSTOM SCRIPTS" checklist). Only read at Load
        History/Start Live click time (see _rebuild_scripts' callers) — the
        same "no retroactive effect" contract RSI/EMA/MACD's toggles already
        have (TC-GAP-07): ticking a box mid-run has no effect until the next
        click.
        """
        return self._view_model.script_model.enabled_keys

    def _rebuild_scripts(self) -> None:
        self._indicator_coordinator.rebuild_scripts()

    def _compute_fetch_limit(self) -> int:
        """BOT-034 — how many candles to fetch, as opposed to how many to
        render. See `IndicatorCoordinator.compute_fetch_limit()` (`EPIC-003G`)."""
        return self._indicator_coordinator.compute_fetch_limit()

    # ================================================================== #
    # Qt Slots — execute on the main thread.
    # Long-running work is delegated to dedicated background methods.
    # ================================================================== #

    @Slot()
    @safe_ui_action
    def _on_load_history(self) -> None:
        self._stream_controller._on_load_history()

    @Slot()
    @safe_ui_action
    def _on_start_stream(self) -> None:
        self._stream_controller._on_start_stream()

    @Slot(str)
    @safe_ui_action
    def _on_stream_start_success(self, msg: str) -> None:
        self._stream_controller._on_stream_start_success(msg)

    @Slot(str)
    @safe_ui_action
    def _on_stream_start_failed(self, msg: str) -> None:
        self._stream_controller._on_stream_start_failed(msg)

    @Slot()
    @safe_ui_action
    def _on_stop_stream(self) -> None:
        self._stream_controller._on_stop_stream()

    @Slot(str)
    @safe_ui_action
    def _on_timeframe_changed(self, timeframe: str) -> None:
        self._stream_controller._on_timeframe_changed(timeframe)

        from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
        from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import (
            TimeFrame,
        )

        bar_seconds = TimeFrame(timeframe).to_seconds()
        max_candles = self.config.get(
            ConfigKeys.CHART_CARD_MAX_ZOOM_OUT_CANDLES.value, 2000, cast=int
        )
        for card in self.active_charts.values():
            card.set_max_visible_x_range(max_candles * bar_seconds)

        # EPIC-010D — the interval lives on this presenter, not the
        # ViewModel, so there is no *Changed signal to hang the debounce off;
        # this is the one place a user can change it.
        self._mark_state_dirty()

    @Slot(str)
    @safe_ui_action
    def _on_near_left_edge(self, symbol: str) -> None:
        """
        @brief BOT-035 — ChartCard.sig_near_left_edge handler.
        @details Only reads the current oldest-loaded timestamp and hands off
        to HistoryPaginationController, which decides whether a fetch is
        actually needed (already-in-flight guard) — this method never
        submits background work itself.
        """
        card = self.active_charts.get(symbol)
        if card is None or not card._raw_history:
            return
        oldest_timestamp = card._raw_history[0][0]
        self._pagination.on_near_left_edge(symbol, oldest_timestamp)

    @Slot(str)
    @safe_ui_action
    def _recheck_edge(self, symbol: str) -> None:
        """Called by HistoryPaginationController after cooldown to check if we still need more data."""
        card = self.active_charts.get(symbol)
        if card:
            card.check_near_left_edge()

    def _fetch_older_history(self, symbol: str, oldest_timestamp: float) -> None:
        self._stream_controller.fetch_older_history(symbol, oldest_timestamp)

    # ================================================================== #
    # Background Signal Slots — called on the main thread via Qt signals.
    # ================================================================== #

    @Slot(str, list, list)
    def _on_history_reloaded(
        self, symbol: str, mapped_data: list, volume_data: list
    ) -> None:
        """Receives pre-mapped kline/volume data from the background and renders to chart."""
        card = self.active_charts.get(symbol)
        if card:
            card.render_historical_data(mapped_data)
            card.render_historical_volume(volume_data)
            self.ui_log_signal.emit(
                f"Refreshed {len(mapped_data)} historical klines for {symbol}."
            )

    @Slot()
    def _on_history_load_finished(self) -> None:
        """Re-enable Dev Board actions after every history-worker outcome."""
        self._view_model.set_history_loading(False)

    @Slot(str, list, list)
    def _on_history_prepended(self, symbol: str, candles: list, volume: list) -> None:
        """
        @brief BOT-035 — receives an older batch from _run_load_more_history
        and prepends it to the chart.
        @details Also rebuilds+refeeds every enabled script over the FULL
        (now-larger) kline history for this symbol — not just the new older
        batch. BaseIndicatorScript has no reset() and only ever computes
        forward through time (see history_pagination_controller.py's
        docstring), so an indicator already warmed up on the old data cannot
        correctly absorb older candles fed in after the fact; a fresh
        rebuild()+feed_all() over the combined history is the only correct
        option with today's script architecture.
        """
        card = self.active_charts.get(symbol)
        if card is None or not candles:
            return
        card.prepend_historical_data(candles)
        card.prepend_historical_volume(volume)
        self.ui_log_signal.emit(f"Loaded {len(candles)} older klines for {symbol}.")

        self._rebuild_scripts()
        self._script_runner.feed_all(self._raw_klines_by_symbol.get(symbol, []))

    @Slot(str, bool)
    def _on_history_prepend_finished(self, symbol: str, found_more: bool) -> None:
        """Unconditional (success, empty result, or error alike) — unlocks
        HistoryPaginationController so the next near-edge pan can fetch
        again. `found_more` is forwarded as-is; see
        HistoryPaginationController.on_load_more_finished's docstring for
        why it gates the auto-recheck."""
        self._pagination.on_load_more_finished(symbol, found_more)

    @Slot(str, list, list)
    def _on_indicator_data(self, name: str, x_data: list, y_data: list) -> None:
        """Pushes a computed indicator script line onto the chart
        (single-symbol Dev Board — see _DEFAULT_SYMBOLS), registering its
        overlay/subplot curve on first use. Every indicator is a script
        (BOT-032 Phase 6 — none are hardcoded), so this is a pure delegate.
        Body in `IndicatorCoordinator` (`EPIC-003G`); this stays a `@Slot`
        because it needs the `QObject`/decorator machinery."""
        self._indicator_coordinator.on_indicator_data(name, x_data, y_data)

    @Slot(str, list)
    def _on_script_region_data(self, key: str, spans: list) -> None:
        """Pushes a script's background-tint spans onto the chart."""
        self._indicator_coordinator.on_script_region_data(key, spans)

    @Slot(str, list)
    def _on_script_info_data(self, key: str, fields: list) -> None:
        """Pushes a script's status-panel fields onto the chart."""
        self._indicator_coordinator.on_script_info_data(key, fields)

    @Slot(str, list)
    def _on_script_marker_data(self, key: str, markers: list) -> None:
        """Pushes a script's Buy/Sell-style labelled markers onto the chart."""
        self._indicator_coordinator.on_script_marker_data(key, markers)

    # ================================================================== #
    # Engine Event Bridge — called from background threads.
    # MUST NOT touch Qt widgets/models here. Use signals only.
    # ================================================================== #

    def _handle_market_tick(self, event: MarketTickEvent) -> None:
        """
        @warning Called by EventBus from a background thread.
        Never touch UI widgets/models here — emit signals only.
        """
        md = event.market_data
        symbol = md.symbol
        is_closed = md.is_closed

        # Only log on candle close to avoid freezing the UI with per-tick log spam.
        if is_closed:
            self.ui_log_signal.emit(
                f"[Live] {symbol} candle closed at {md.close_price}"
            )

        self.ui_chart_update_signal.emit(
            symbol,
            md.close_time.timestamp(),
            float(md.open_price),
            float(md.high_price),
            float(md.low_price),
            float(md.close_price),
            float(md.volume),
            is_closed,
        )

    @Slot(str, float, float, float, float, float, float, bool)
    def _on_ui_chart_update(
        self,
        symbol: str,
        t: float,
        o: float,
        h: float,
        low: float,
        c: float,
        volume: float,
        is_closed: bool,
    ) -> None:
        """
        @brief Được gọi trong Main UI Thread một cách an toàn thông qua Signal.
        Chỉ thực hiện tra cứu O(1) và đẩy data vào đúng ChartCard tương ứng.
        """
        # BOT-034 — any tick is proof of a real connection, cancelling the
        # auto-start fallback timer. Must happen here (main thread), NOT in
        # _handle_market_tick (background thread) — QTimer.stop() from a
        # foreign thread is a Qt threading violation. `_autostart` is None
        # when BOT-062's config gate is off (the default) — nothing to
        # cancel in that case.
        if self._autostart is not None:
            self._autostart.on_market_tick()

        is_bullish = c >= o
        price_color = BULL_COLOR if is_bullish else BEAR_COLOR
        self._view_model.set_price_ticker(f"{symbol}  {c:,.2f}", price_color)

        card = self.active_charts.get(symbol)
        if card:
            if is_closed:
                card.append_closed_candle(t, o, h, low, c)
                card.append_closed_volume(t, volume, is_bullish)
                candle = _tick_to_candle(
                    symbol, self._active_interval, t, o, h, low, c, volume
                )
                # BOT-035 — keep the raw-kline cache (used to rebuild+refeed
                # scripts after a later load-more prepend) in sync with what
                # the chart actually shows; otherwise a prepend's rebuild
                # would silently drop every candle that arrived live since
                # the last full Load History/Start Live.
                raw_list = self._raw_klines_by_symbol.setdefault(symbol, [])
                if raw_list and raw_list[-1].close_time == candle.close_time:
                    raw_list[-1] = candle
                else:
                    raw_list.append(candle)
                self._script_runner.feed(candle)
            else:
                card.update_last_candle(t, o, h, low, c)
                card.update_last_volume(t, volume, is_bullish)

    # ================================================================== #
    # Background methods — submitted to IThreadManager.
    # MUST NOT touch Qt widgets/models directly. Use signals only.
    # ================================================================== #
