from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from PySide6.QtCore import Signal, Slot
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.market_tick_event import (
    MarketTickEvent,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.market_tick_feed import (
    MarketTickFeed,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.sync_progress_feed import (
    SyncProgressFeed,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.emergency_stop_result import (
    EmergencyStopResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.enable_trading_result import (
    EnableTradingBlockReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.equity_sampled_event import (
    EquitySampledEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.live_order_blocked_event import (
    LiveOrderBlockedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_filled_event import (
    OrderFilledEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.position_changed_event import (
    PositionChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.position_closed_event import (
    PositionClosedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.equity_chart_adapter import (
    equity_sample_to_candle,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.equity_feed import EquityFeed
from Sagittarius_Elite_Warrior.src.modules.trading.ui.execute_order_block_reason import (
    format_execute_order_block_reason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_feed import OrderFeed
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_fill_marker import (
    order_filled_marker,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.signal_feed import SignalFeed
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.theme import (
    BEAR_COLOR,
    BULL_COLOR,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.action_ownership_tracker import (
    ActionOutcome,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.app_defaults import (
    FALLBACK_INTERVAL,
    FALLBACK_SYMBOL,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.assets import Palette
from Sagittarius_Elite_Warrior.src.support.ui_kit.constants import UIMode
from Sagittarius_Elite_Warrior.src.support.ui_kit.enum_labels import EnumLabels
from Sagittarius_Elite_Warrior.src.support.ui_kit.health_check_coordinator import (
    HealthCheckCoordinator,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.state.state_scope import (
    StateData,
    StateScope,
)
from sagittarius_engine.extensions.pyside_mvc import BasePresenter, safe_ui_action

from .dashboard_view_model import (
    DATETIME_FORMAT,
    DEFAULT_LOOKBACK_DAYS,
)
from .logic.chart_zoom_limits import max_visible_x_range
from .logic.presenter_factory import (
    _EMERGENCY_STOP_ACTION,
    _MANUAL_ORDER_ACTION,
    _TOGGLE_ACTION,
    build_dashboard_presenter_state,
)

logger = logging.getLogger("App.Dashboard")

if TYPE_CHECKING:
    from collections.abc import Callable

    from Sagittarius_Elite_Warrior.src.modules.market_data.ui.symbol_options_coordinator import (
        SymbolOptionsCoordinator,
    )
    from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_snapshot import (
        IAccountSnapshot,
    )
    from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_armed_strategy_reader import (
        IArmedStrategyReader,
    )
    from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_equity_curve import (
        IEquityCurve,
    )
    from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_order_submission import (
        IOrderSubmission,
    )
    from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_session import (
        ITradingSession,
    )
    from Sagittarius_Elite_Warrior.src.modules.trading.ui.dashboard.autostart_controller import (
        AutoStartController,
    )
    from Sagittarius_Elite_Warrior.src.modules.trading.ui.dashboard.coordinators.indicator_coordinator import (
        IndicatorCoordinator,
    )
    from Sagittarius_Elite_Warrior.src.modules.trading.ui.dashboard.coordinators.trading_actions_coordinator import (
        TradingActionsCoordinator,
    )
    from Sagittarius_Elite_Warrior.src.modules.trading.ui.dashboard.dashboard_view import (
        DashboardView,
    )
    from Sagittarius_Elite_Warrior.src.modules.trading.ui.dashboard.dashboard_view_model import (
        DashboardQmlViewModel,
    )
    from Sagittarius_Elite_Warrior.src.modules.trading.ui.dashboard.history_pagination_controller import (
        HistoryPaginationController,
    )
    from Sagittarius_Elite_Warrior.src.modules.trading.ui.dashboard.stream_lifecycle_controller import (
        StreamLifecycleController,
    )
    from Sagittarius_Elite_Warrior.src.modules.trading.ui.live_order_book_coordinator import (
        LiveOrderBookCoordinator,
    )
    from Sagittarius_Elite_Warrior.src.modules.trading.ui.strategy_arming_coordinator import (
        StrategyArmingCoordinator,
    )
    from Sagittarius_Elite_Warrior.src.support.indicators.indicator_script_catalog import (
        IndicatorScriptCatalog,
    )
    from Sagittarius_Elite_Warrior.src.support.indicators.indicator_script_params_store import (
        IndicatorScriptParamsStore,
    )
    from Sagittarius_Elite_Warrior.src.support.indicators.indicator_script_registry import (
        IndicatorScriptRegistry,
    )
    from Sagittarius_Elite_Warrior.src.support.indicators.ui.runner import (
        IndicatorScriptRunner,
    )
    from Sagittarius_Elite_Warrior.src.support.ui_kit.action_ownership_tracker import (
        ActionOwnershipTracker,
    )
    from Sagittarius_Elite_Warrior.src.support.ui_kit.state.ui_state_coordinator import (
        UiStateCoordinator,
    )
    from sagittarius_engine.interfaces.i_container import IContainer
    from sagittarius_engine.interfaces.i_thread_manager import IThreadManager
    from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken

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

#: `BOT-144` — moved into `logic/presenter_factory.py` alongside the
#: construction code that primarily uses them (`build_dashboard_presenter_state`);
#: imported back here for the methods below that still read them
#: (`_on_enable_trading_completed` etc. for the `_*_ACTION` kinds — see the
#: import block above this class).
#: BOT-035 — how many older candles to fetch each time the user scrolls near
#: the left edge of loaded history. User-configurable (IConfig key), but
#: deliberately NOT run through _compute_fetch_limit() — this is a literal
#: "load N more" action, not a warm-up requirement, so it doesn't grow with
#: whatever scripts happen to be enabled.
_LOAD_MORE_BATCH_CANDLES_CONFIG_KEY: str = "CHART_CARD_LOAD_MORE_BATCH_CANDLES"
_DEFAULT_LOAD_MORE_BATCH_CANDLES: int = 75

#: `EPIC-021K` §2.3/§3 — live-fill trade markers, same key `TradingPresenter`
#: uses (separate `MarkerLayer` per `ChartCard`, so no collision between screens).
_FILL_MARKERS_KEY = "live_fills"

#: `PRO-003` §4.1.2's message for the hard block on the strategy's armed
#: symbol used to live here. `EPIC-025` PR 2.1f moved the rule onto the order
#: path — `ExecuteOrderSafetyGate.SYMBOL_LEASED`, refused against `trading`'s
#: symbol lease — so the text lives with the other gate messages in
#: `ui/common/execute_order_block_reason.py`, word for word. The user's
#: decision did not change; the layer that enforces it did.

#: `EnumLabels`, not a bare dict — same reasoning `TradingPresenter`'s own
#: `_BLOCK_REASON_MESSAGES` documents: construction refuses an incomplete
#: table rather than letting a `.get(..., generic)` silently hide a missing
#: refusal message.
_BLOCK_REASON_MESSAGES = EnumLabels(
    EnableTradingBlockReason,
    {
        EnableTradingBlockReason.TRADING_VENUE_DISABLED: (
            "Trading venue is disabled in configuration — only Futures Testnet is supported."
        ),
        EnableTradingBlockReason.CONNECTION_NOT_READY: (
            "Connection to the exchange is not ready — check your API key/network connection."
        ),
        EnableTradingBlockReason.UNEXPECTED_POSITIONS: (
            "The account has unexpected open positions — please handle them manually "
            "on the exchange before enabling trading."
        ),
        EnableTradingBlockReason.SUPERSEDED_BY_CONCURRENT_STATE_CHANGE: (
            "Another operation (usually EMERGENCY STOP) changed the state while "
            "reconciliation was in progress — trading was not enabled. Check the "
            "state and try again if you still want to enable it."
        ),
    },
)

# WS status badge (top bar) text/color/tone per FSM state — presentational
# only, derived from the state DashboardPresenter already tracks.
#
# `tone` (third element) is `WsStatusPill`'s semantic vocabulary
# ("idle"|"active"|"success"|"danger" — see that file's own docstring).
# `EPIC-015` Phase 4 added it here, as a third element of the SAME dict,
# rather than a second `UIMode -> tone` switch: the tone for a mode is a
# property of that mode's row, not an independent fact that could drift
# out of sync with its text/colour. Do NOT derive `tone` from `color`
# (a Palette hex string, or `BULL_COLOR`/`BEAR_COLOR`) — that would break
# silently if any of those values ever changed, since a colour string
# carries no semantic meaning `WsStatusPill` could read back out of it.
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
    # Luật đầy đủ + số liệu đo thật: .claude/rules/architecture-rule.md §6.
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

    # BOT-123 — Start Live's sync-from-Binance phase, forwarded straight to
    # DashboardQmlViewModel.set_progress's own (int, int, bool, str) Slot
    # overload (same shape/connect pattern as DataManagementPresenter's
    # ui_single_sync_progress_signal). StreamLifecycleController.on_sync_progress
    # is the only thing that calls this — see that method's docstring for the
    # correlation_id filtering that makes cross-screen sync-progress fan-out
    # (BOT-121/BOT-122) safe here too.
    ui_sync_progress_signal = Signal(int, int, bool, str)

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

    #: `EPIC-023D` — Enable/Disable trading + Emergency Stop, same worker-
    #: boundary shape `TradingPresenter` uses for its own three signals.
    #: `(action_id, EnableTradingResult | None, error_message | None)`.
    enableTradingCompleted = Signal(tuple)
    #: `(action_id, error_message | None)`.
    disableTradingCompleted = Signal(tuple)
    #: `(action_id, EmergencyStopResult | None, error_message | None)`.
    emergencyStopCompleted = Signal(tuple)

    #: `EPIC-024B` — manual trading card + per-order cancel.
    #: `(action_id, ExecuteOrderResult | None, error_message | None)`. The
    #: `strategy_conflict: bool` that used to sit third is gone with the
    #: screen's own hard block (PR 2.1f): an armed symbol now comes back as
    #: `ExecuteOrderSafetyGate.SYMBOL_LEASED` on the result, which is the same
    #: shape every other refusal already used.
    manualOrderCompleted = Signal(tuple)
    #: `(symbol, client_order_id, CancelOrderResult | None,
    #: error_message | None)`.
    cancelOrderCompleted = Signal(tuple)

    INITIAL_STATE = UIMode.IDLE

    #: `BOT-144` — declared here, not just assigned inside
    #: `build_dashboard_presenter_state()`: every one of these used to be
    #: inferrable from a `self.x = ...` line inside `__init__` itself, which
    #: is how a type checker (and a reader) normally learns a class's
    #: instance-attribute surface. Moving the assignments into an external
    #: Builder function broke that inference silently — nothing raised, mypy
    #: just stopped seeing these attributes exist — so they are restated
    #: explicitly here instead. This file is mypy-excluded (see
    #: `pyproject.toml`'s `[tool.mypy]` exclude list) so these are not
    #: self-checked, but `logic/presenter_factory.py` — which is checked —
    #: reads `presenter.<name>` throughout and needs this declared shape.
    _view_model: DashboardQmlViewModel
    _thread_manager: IThreadManager
    _trading_session: ITradingSession
    _order_submission: IOrderSubmission
    _account: IAccountSnapshot
    _equity_curve: IEquityCurve
    _symbol_options_coordinator: SymbolOptionsCoordinator
    _cancellation_token: CancellationToken
    _shutdown_requested: bool
    active_charts: dict
    _raw_klines_by_symbol: dict[str, list]
    _fill_markers_by_symbol: dict[str, list]
    _order_book: LiveOrderBookCoordinator
    _armed_strategy: IArmedStrategyReader
    _arm_tracker: ActionOwnershipTracker[str, None, None]
    _arming_coordinator: StrategyArmingCoordinator
    _toggle_tracker: ActionOwnershipTracker[str, None, None]
    _emergency_stop_tracker: ActionOwnershipTracker[str, None, None]
    _manual_order_tracker: ActionOwnershipTracker[str, None, None]
    _last_price_by_symbol: dict[str, Decimal]
    _trading_actions: TradingActionsCoordinator
    _pagination: HistoryPaginationController
    _active_interval: str
    _active_symbol: str
    _script_registry: IndicatorScriptRegistry
    _script_catalog: IndicatorScriptCatalog
    _script_params_store: IndicatorScriptParamsStore
    _script_runner: IndicatorScriptRunner
    _indicator_coordinator: IndicatorCoordinator
    _stream_controller: StreamLifecycleController
    _run_load_history: Callable[..., None]
    _run_load_more_history: Callable[..., None]
    _run_sync_and_start: Callable[..., None]
    _state_coordinator: UiStateCoordinator | None
    _autostart: AutoStartController | None

    def __init__(self, view: DashboardView, container: IContainer) -> None:
        super().__init__(view, container)

        build_dashboard_presenter_state(self, view, container)

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
        self._symbol_options_coordinator.request_open()

    @Slot()
    def _on_symbol_picker_refresh_requested(self) -> None:
        """Forces a refresh of the symbol options directly from the exchange
        (`BUG-066`'s manual 🔄, bypassing both the coordinator's and
        `ISymbolCatalogRepository`'s cache)."""
        self._symbol_options_coordinator.request_refresh()

    @Slot(list)
    def _on_symbol_options_ready(self, symbols: list[str]) -> None:
        self._symbol_options_coordinator.on_options_ready(symbols)
        self._view_model.set_symbol_options(symbols)

    @Slot(str)
    def _on_symbol_options_failed(self, message: str) -> None:
        self._append_log(f"[ERROR] Failed to load symbol list: {message}")

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
        if hasattr(self, "_stream_controller") and self._stream_controller is not None:
            self._stream_controller.shutdown()
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
        view_model.symbolOptionsRefreshRequested.connect(
            self._on_symbol_picker_refresh_requested
        )
        self._symbolOptionsReadySignal.connect(self._on_symbol_options_ready)
        self._symbolOptionsFailedSignal.connect(self._on_symbol_options_failed)

        # `EPIC-023C` — strategy card, same connections `TradingPresenter`
        # makes for the identical ViewModel signals.
        view_model.strategy.strategyConfigChanged.connect(
            self._on_strategy_selection_changed
        )
        view_model.strategy.botParamsSaveRequested.connect(
            self._on_bot_params_save_requested
        )
        view_model.strategy.armRequested.connect(self._on_arm_requested)
        view_model.strategy.disarmRequested.connect(self._on_disarm_requested)

        # `EPIC-023D` — Enable/Disable trading + Emergency Stop, same
        # connections `TradingPresenter` makes for the identical ViewModel
        # signals.
        view_model.toggleRequested.connect(self._on_toggle_requested)
        view_model.emergencyStopRequested.connect(self._on_emergency_stop_requested)
        self.enableTradingCompleted.connect(self._on_enable_trading_completed)
        self.disableTradingCompleted.connect(self._on_disable_trading_completed)
        self.emergencyStopCompleted.connect(self._on_emergency_stop_completed)

        # `EPIC-024B` — manual trading card + per-order cancel.
        view_model.manualOrderRequested.connect(self._on_manual_order_requested)
        self.manualOrderCompleted.connect(self._on_manual_order_completed)
        self.view.cancelOrderRequested.connect(self._on_cancel_order_requested)
        self.cancelOrderCompleted.connect(self._on_cancel_order_completed)

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
        self.ui_sync_progress_signal.connect(view_model.set_progress)
        self.ui_indicator_data_signal.connect(self._on_indicator_data)
        self.ui_script_region_signal.connect(self._on_script_region_data)
        self.ui_script_info_signal.connect(self._on_script_info_data)
        self.ui_script_marker_signal.connect(self._on_script_marker_data)

    def _connect_engine_events(self) -> None:
        """Đăng ký lắng nghe sự kiện từ Engine EventBus."""
        # `MarketTickEvent` giờ đi qua `MarketTickFeed` — một nơi nghe, nhiều
        # màn hiển thị (`architecture-rule.md` §6), cùng lý do `HealthFeed`/
        # `SyncProgressFeed` bên dưới tồn tại. Trước đây màn này tự
        # `event_bus.on(MarketTickEvent, ...)`, và `EPIC-021I`'s Trading màn
        # cũng tự làm y hệt — đúng lớp trùng lặp `test_event_flow_guards.py`
        # bắt được (`EPIC-008G`'s `HealthUpdatedEvent` defect, tái diễn).
        self._market_tick_feed = MarketTickFeed(self.event_bus, parent=self)
        self._market_tick_feed.marketTick.connect(self._handle_market_tick)
        # Sức khoẻ hệ thống là sự thật của HỆ THỐNG, không riêng màn này, nên nó
        # đi qua HealthFeed — một nơi nghe, nhiều màn hiển thị
        # (`architecture-rule.md` §6). Trước đây màn này tự `event_bus.on(...)`
        # rồi tự ghép chuỗi, và Backtest cũng vậy: 2 định dạng khác nhau cho
        # cùng một dữ liệu, bản của Backtest còn mất hẳn `Container`. Wiring
        # đó (dựng `HealthFeed`, connect, hỏi lúc mở màn) lại trùng lặp giữa
        # 2 Presenter — `HealthCheckCoordinator` (`EPIC-019B`) dùng chung.
        self._health_check_coordinator = HealthCheckCoordinator(
            event_bus=self.event_bus,
            emit_log=self.ui_log_signal.emit,
            parent=self,
        )
        # Tiến độ đồng bộ là sự thật của HỆ THỐNG (Backtest, Data Management
        # cũng hiển thị) → đi qua SyncProgressFeed, một nơi chuẩn hoá + ghép
        # chuỗi (`architecture-rule.md` §6), thay vì màn này tự
        # `event_bus.on(SingleSyncProgressEvent, ...)` và tự ghép câu chữ lần
        # thứ ba (BOT-123).
        self._sync_feed = SyncProgressFeed(self.event_bus, parent=self)
        self._sync_feed.progressUpdated.connect(self._on_sync_progress)
        # `EPIC-021K` §2.3/§3 — live order fills as chart markers; `EPIC-023A`
        # widens this same Feed instance to also keep the Vị thế/Lệnh chờ
        # khớp tables live (`positionChanged`/`positionClosed`/`orderBlocked`
        # — previously only `orderFilled` was read here). `OrderFeed` already
        # exists for `TradingPresenter` (`EPIC-021H`), so this is a second
        # consumer of the same one-place-subscribes Feed, not a new
        # subscription shape.
        self._order_feed = OrderFeed(self.event_bus, parent=self)
        self._order_feed.orderFilled.connect(self._on_order_filled)
        self._order_feed.positionChanged.connect(self._on_position_changed)
        self._order_feed.positionClosed.connect(self._on_position_closed)
        self._order_feed.orderBlocked.connect(self._on_order_blocked)
        # `EPIC-023B` — same one-place-subscribes Feed `TradingPresenter`
        # already uses (`EPIC-021M`); a second consumer, not a new shape.
        self._equity_feed = EquityFeed(self.event_bus, parent=self)
        self._equity_feed.equitySampled.connect(self._on_equity_sampled)
        # `EPIC-023C` — same shared bus `TradingPresenter` reads
        # `SignalGeneratedEvent` from (`EPIC-022E`); a second consumer.
        self._signal_feed = SignalFeed(self.event_bus, parent=self)
        self._signal_feed.signalGenerated.connect(
            self._arming_coordinator.on_signal_generated
        )

    def _trigger_initial_health_check(self) -> None:
        self._health_check_coordinator.request_initial_check()

    def _on_sync_progress(self, report) -> None:
        """`SyncProgressFeed.progressUpdated` handler — already on the main
        thread. Delegates the correlation_id filtering to
        `StreamLifecycleController.on_sync_progress` (BOT-123), which owns
        the id this screen's own in-flight sync is using."""
        self._stream_controller.on_sync_progress(report)

    def _on_order_filled(self, event: OrderFilledEvent) -> None:
        """`OrderFeed.orderFilled` handler — already on the main thread.

        @details Two independent effects:
        1. Lệnh chờ khớp table bookkeeping — delegated to
           `LiveOrderBookCoordinator` (`EPIC-023A` follow-up: this used to
           be a byte-for-byte copy of `TradingPresenter`'s own dict/render
           logic, pulled out once duplicated a second time — same class of
           defect `health_check_coordinator.py`'s own docstring names).
        2. Draws a chart marker, only when a chart card for that symbol is
           currently open (`active_charts`); a fill on a symbol Dev Board
           isn't showing has nowhere to draw and is silently dropped, same
           as `TradingPresenter._record_fill_marker`'s
           `symbol == self._active_symbol` guard for its single chart. This
           half stays here — it is genuinely screen-specific, unlike #1.
        3. `EPIC-023D` — refreshes the session-stats card, same as
           `TradingPresenter._on_order_filled`.
        """
        self._order_book.on_order_filled(event.order)
        self._refresh_session_stats()

        symbol = event.order.symbol
        card = self.active_charts.get(symbol)
        if card is None:
            return
        markers = self._fill_markers_by_symbol.setdefault(symbol, [])
        markers.append(order_filled_marker(event))
        card.set_script_markers(_FILL_MARKERS_KEY, markers)

    def _on_position_changed(self, event: PositionChangedEvent) -> None:
        """`OrderFeed.positionChanged` handler — already on the main thread."""
        self._order_book.on_position_changed(event.position)

    def _on_position_closed(self, event: PositionClosedEvent) -> None:
        """`OrderFeed.positionClosed` handler — already on the main thread.
        `BUG-086`."""
        self._order_book.on_position_closed(event.symbol)

    def _on_order_blocked(self, event: LiveOrderBlockedEvent) -> None:
        """`OrderFeed.orderBlocked` handler — already on the main thread.
        `BUG-084`."""
        self._order_book.on_order_blocked(event.symbol, event.reason)

    def _refresh_session_stats(self) -> None:
        # One snapshot for both numbers: they describe the same moment, and
        # `TradingSessionSnapshot` is what makes that guarantee.
        session = self._trading_session.snapshot()
        self._view_model.set_session_stats(
            session.orders_sent_this_session,
            len(session.known_open_symbols),
        )

    def _on_equity_sampled(self, event: EquitySampledEvent) -> None:
        """`EquityFeed.equitySampled` handler — already on the main thread.
        Account-wide (no per-symbol filtering), same as `TradingPresenter`'s
        own handler."""
        self.view.equity_chart.append_closed_candle(
            *equity_sample_to_candle(event.sample)
        )

    # ================================================================== #
    # Enable/Disable trading toggle (`EPIC-023D`) — a single async action,
    # fenced with `ActionOwnershipTracker`, same pattern `TradingPresenter`
    # uses for its own identical toggle. `ITradingSession.enable()`/`disable()`
    # are account-wide (the port is a DI singleton over one session state),
    # so a click here has the exact same effect a click on
    # Trading's own toggle would — deliberately: see `EPIC-023`'s README §2.
    #
    # Unlike Trading, there is no `_go_live_if_not_already()` call on a
    # successful enable: Dev Board's chart liveness is already governed
    # independently by its own Load History/Start Live buttons (and
    # `DEV_BOARD_AUTOSTART_ENABLED`), so enabling trading here must not
    # also force the chart into live mode as a side effect.
    # ================================================================== #

    @Slot()
    @safe_ui_action
    def _on_toggle_requested(self) -> None:
        self._trading_actions.request_toggle()

    @Slot(tuple)
    def _on_enable_trading_completed(self, payload: tuple) -> None:
        action_id, result, error = payload
        if not self._toggle_tracker.is_current_pending(action_id, _TOGGLE_ACTION):
            self._toggle_tracker.log_stale_callback(
                "enable_trading", action_id, _TOGGLE_ACTION
            )
            return

        if error is not None or result is None:
            self._toggle_tracker.finish_action(action_id, ActionOutcome.FAILED)
            self._view_model.set_trading_state(
                self._trading_session.snapshot().enabled, False
            )
            self._append_log(f"Error enabling trading: {error}")
            return

        self._toggle_tracker.finish_action(action_id, ActionOutcome.SUCCEEDED)
        self._view_model.set_trading_state(result.enabled, False)
        if result.enabled:
            self._append_log("Trading enabled.")
            # A refusal is the only path that ever returns a non-empty
            # `reconciled_positions` (see `ITradingSession.enable()`) —
            # a successful enable therefore always starts with none open.
            self._order_book.replace_all(
                positions=[], open_orders=result.reconciled_open_orders
            )
        else:
            self._append_log(_BLOCK_REASON_MESSAGES[result.block_reason])
            self._order_book.replace_all(
                positions=result.reconciled_positions,
                open_orders=result.reconciled_open_orders,
            )
        self._refresh_session_stats()

    @Slot(tuple)
    def _on_disable_trading_completed(self, payload: tuple) -> None:
        action_id, error = payload
        if not self._toggle_tracker.is_current_pending(action_id, _TOGGLE_ACTION):
            self._toggle_tracker.log_stale_callback(
                "disable_trading", action_id, _TOGGLE_ACTION
            )
            return

        if error is not None:
            self._toggle_tracker.finish_action(action_id, ActionOutcome.FAILED)
            self._view_model.set_trading_state(
                self._trading_session.snapshot().enabled, False
            )
            self._append_log(f"Error disabling trading: {error}")
            return

        self._toggle_tracker.finish_action(action_id, ActionOutcome.SUCCEEDED)
        self._view_model.set_trading_state(False, False)
        self._append_log("Trading disabled.")

    # ================================================================== #
    # Emergency Stop (`EPIC-023D`) — the request/run halves live on
    # `TradingActionsCoordinator` now (`BOT-144`); deliberately NOT
    # `@safe_ui_action` here (that decorator swallows exceptions; this
    # button's whole point is that a failure must be seen, never silently
    # dropped mid-flow — ONBOARDING.md §8, bẫy 8), same reasoning
    # `TradingPresenter` documents for its own identical button.
    # ================================================================== #

    @Slot()
    def _on_emergency_stop_requested(self) -> None:
        self._trading_actions.request_emergency_stop()

    @Slot(tuple)
    def _on_emergency_stop_completed(self, payload: tuple) -> None:
        action_id, result, error = payload
        if not self._emergency_stop_tracker.is_current_pending(
            action_id, _EMERGENCY_STOP_ACTION
        ):
            self._emergency_stop_tracker.log_stale_callback(
                "emergency_stop", action_id, _EMERGENCY_STOP_ACTION
            )
            return

        if error is not None or result is None:
            self._emergency_stop_tracker.finish_action(action_id, ActionOutcome.FAILED)
            self._view_model.set_trading_state(
                self._trading_session.snapshot().enabled, False
            )
            self._append_log(f"[ERROR] Emergency stop failed: {error}")
            return

        self._emergency_stop_tracker.finish_action(
            action_id,
            ActionOutcome.SUCCEEDED if result.fully_succeeded else ActionOutcome.FAILED,
        )
        self._view_model.set_trading_state(
            self._trading_session.snapshot().enabled, False
        )
        self._log_emergency_stop_result(result)
        self._apply_emergency_stop_final_state(result)
        if result.fully_succeeded:
            self._append_log("Emergency stop completed.")
        else:
            self._append_log("EMERGENCY STOP — PARTIALLY FAILED. See the log.")

    def _apply_emergency_stop_final_state(self, result: EmergencyStopResult) -> None:
        """`BUG-093` (Trading's own precedent) — the user-data stream is
        already stopped by Emergency Stop's own step 1, so
        `_on_order_filled`/`_on_position_changed`/`_on_position_closed` will
        never fire for whatever steps 2-3 actually did. Without this, the
        Positions/Open Orders tables keep showing whatever they held right
        before the button was pressed."""
        if not result.final_state_confirmed:
            self._append_log(
                "[WARNING] Could not confirm account state after the emergency "
                "stop — the positions/open orders table below may no longer be "
                "accurate. Run `exchange-status` to check directly."
            )
            return
        self._order_book.replace_all(
            positions=result.final_positions, open_orders=result.final_open_orders
        )

    def _log_emergency_stop_result(self, result: EmergencyStopResult) -> None:
        self._append_log("EMERGENCY STOP")
        for index, (label, step) in enumerate(
            (
                ("Disable trading", result.trading_disabled),
                ("Cancel pending orders", result.orders_cancelled),
                ("Close positions", result.positions_closed),
            ),
            start=1,
        ):
            mark = "✔" if step.succeeded else "✘"
            self._append_log(f"  {index}. {label} ... {mark} {step.detail}")

    # ================================================================== #
    # Manual trading card (`EPIC-024B`) — the first UI path that dispatches
    # `IOrderSubmission.submit()` from a human click rather than a strategy tick
    # (`LiveTradingCoordinator`). Deliberately reuses that exact command/
    # handler — see `PRO-003`/`EPIC-024B` §4: this task exists to prove the
    # mechanism generalizes to a second caller, not to build a second path.
    # ================================================================== #

    @Slot(str, float, str, float)
    @safe_ui_action
    def _on_manual_order_requested(
        self, direction_text: str, quantity: float, order_type_text: str, price: float
    ) -> None:
        self._trading_actions.request_manual_order(
            direction_text, quantity, order_type_text, price
        )

    @Slot(tuple)
    def _on_manual_order_completed(self, payload: tuple) -> None:
        action_id, result, error = payload
        if not self._manual_order_tracker.is_current_pending(
            action_id, _MANUAL_ORDER_ACTION
        ):
            self._manual_order_tracker.log_stale_callback(
                "manual_order", action_id, _MANUAL_ORDER_ACTION
            )
            return

        if error is not None or result is None:
            self._manual_order_tracker.finish_action(action_id, ActionOutcome.FAILED)
            message = f"Error placing manual order: {error}"
            self._view_model.set_manual_order_state(False, message)
            self._append_log(message)
            return

        if result.blocked:
            self._manual_order_tracker.finish_action(action_id, ActionOutcome.FAILED)
            message = (
                f"Manual order blocked: "
                f"{format_execute_order_block_reason(result.blocked_by)}"
            )
            self._view_model.set_manual_order_state(False, message)
            self._append_log(message)
            return

        self._manual_order_tracker.finish_action(action_id, ActionOutcome.SUCCEEDED)
        order = result.submitted_order
        message = f"Manual order placed: {order.client_order_id if order else '—'}"
        self._view_model.set_manual_order_state(False, message)
        self._append_log(message)
        self._refresh_session_stats()

    # ================================================================== #
    # Per-order cancel (`EPIC-024B` §0) — the Open Orders table's "Huỷ"
    # button. No `ActionOwnershipTracker`: unlike the manual order card
    # (one card, one pending attempt at a time), cancelling order A and
    # cancelling a different order B on another row are genuinely
    # independent actions — fencing them through one tracker would let a
    # second row's cancel wrongly invalidate the first row's.
    # ================================================================== #

    @Slot(str, str)
    @safe_ui_action
    def _on_cancel_order_requested(self, symbol: str, client_order_id: str) -> None:
        self._trading_actions.request_cancel_order(symbol, client_order_id)

    @Slot(tuple)
    def _on_cancel_order_completed(self, payload: tuple) -> None:
        symbol, client_order_id, result, error = payload
        if error is not None or result is None:
            self._append_log(f"Error cancelling order {client_order_id}: {error}")
            return
        if result.blocked:
            self._append_log(
                f"Cancel order blocked: {format_execute_order_block_reason(result.blocked_by)}"
            )
            return
        self._order_book.on_order_cancelled(client_order_id)
        self._append_log(f"Order {client_order_id} ({symbol}) cancelled.")

    # ================================================================== #
    # Strategy card (`EPIC-023C`) — the button handlers live in
    # `StrategyArmingCoordinator`; what stays here is what this Presenter
    # genuinely owns, same split `TradingPresenter` documents for itself.
    # ================================================================== #

    @Slot()
    def _on_strategy_selection_changed(self) -> None:
        self._arming_coordinator.on_strategy_selection_changed()

    @Slot("QVariantMap")
    @safe_ui_action
    def _on_bot_params_save_requested(self, values: dict) -> None:
        if self._arming_coordinator.apply_params(values):
            self._append_log("Strategy Parameters saved.")

    @Slot()
    def _on_arm_requested(self) -> None:
        self._arming_coordinator.on_arm_clicked()

    @Slot()
    def _on_disarm_requested(self) -> None:
        self._arming_coordinator.on_disarm_clicked()

    def _on_armed_config_changed(self, config, busy: bool) -> None:
        """Called by the Coordinator whenever what is armed may have
        changed. No chart overlay to keep in step here (`EPIC-022`'s
        indicator/trend-region drawing stays Trading-only — Dev Board's own
        chart cards already exist for the indicator-script testbed this
        screen was built for)."""
        self._view_model.strategy.set_armed_summary(
            self._arming_coordinator.armed_summary(config), busy
        )

    def _refresh_armed_summary(self, *, busy: bool) -> None:
        self._on_armed_config_changed(self._armed_strategy.armed().config, busy)

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

        x_range = max_visible_x_range(self.config, self._active_interval)

        for card in chart_cards:
            self.active_charts[card.symbol] = card
            card.set_max_visible_x_range(x_range)
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

        x_range = max_visible_x_range(self.config, timeframe)
        for card in self.active_charts.values():
            card.set_max_visible_x_range(x_range)

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
    # Engine Event Bridge — reached via `MarketTickFeed`, already marshaled
    # onto the main Qt thread by its `QtEventBridge` (`BaseFeed`'s own
    # contract). Kept emitting signals only, not touching widgets directly,
    # so this method's own behaviour is unchanged either way.
    # ================================================================== #

    def _handle_market_tick(self, event: MarketTickEvent) -> None:
        """Delegates to `ui_chart_update_signal` rather than touching
        `active_charts`/`ChartCard` directly — keeps one path for both a
        same-thread (here) and a cross-thread emitter to update the chart."""
        md = event.market_data
        # `BOT-126` — same fault `BUG-085` fixed for `MarketTickEventHandler`,
        # never applied here: a stream now genuinely can carry more than one
        # interval for the same symbol at once (this screen and Trading each
        # own their own subscription), and this screen's own chart cards all
        # share one `self._active_interval` — a tick at any other interval
        # would otherwise be drawn as if it belonged to the selected one.
        if md.interval != self._active_interval:
            return
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
        # `EPIC-024B` — manual order card's MARKET reference price.
        self._last_price_by_symbol[symbol] = Decimal(str(c))

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
