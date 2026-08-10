from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from Binace_Bot.src.application.services.indicator_script_registry import (
    IndicatorScriptRegistry,
)
from Binace_Bot.src.application.use_cases.queries.get_historical_klines.query import (
    GetHistoricalKlinesQuery,
)
from Binace_Bot.src.application.use_cases.stream.start_live_stream.command import (
    StartLiveStreamCommand,
)
from Binace_Bot.src.application.use_cases.stream.stop_live_stream.command import (
    StopLiveStreamCommand,
)
from Binace_Bot.src.application.use_cases.sync.sync_market_data.command import (
    SyncMarketDataCommand,
)
from Binace_Bot.src.domain.entities.market_data import MarketData
from Binace_Bot.src.domain.events.market_tick_event import MarketTickEvent
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame
from Binace_Bot.src.presentation.ui.components.chart_card.theme import (
    BEAR_COLOR,
    BULL_COLOR,
)
from Binace_Bot.src.presentation.ui.constants import UIMode
from PySide6.QtCore import Signal, Slot
from sagittarius_engine.extensions.pyside_mvc import BasePresenter, safe_ui_action
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken

from .autostart_controller import AutoStartController
from .dashboard_view_model import DashboardQmlViewModel
from .history_pagination_controller import HistoryPaginationController
from .indicator_script_runner import IndicatorScriptRunner

if TYPE_CHECKING:
    from Binace_Bot.src.presentation.ui.screens.dashboard.dashboard_view import (
        DashboardView,
    )
    from sagittarius_engine.interfaces.i_container import IContainer

# ---------------------------------------------------------------------------
# Constants — no magic values scattered in method bodies
# ---------------------------------------------------------------------------
_DEFAULT_SYMBOLS: tuple[str, ...] = ("ETHUSDT",)
_DEFAULT_INTERVAL_STR: str = "1m"

# BOT-034 — how many candles to RENDER is not how many to FETCH: 75 is what
# the chart shows by default (see ChartCard._DEFAULT_INITIAL_VISIBLE_CANDLES,
# a separate, zoom-level concept this doesn't replace), but a script's
# slowest indicator may need far more history than that just to produce its
# first point. _compute_fetch_limit() reconciles the two.
_RENDER_WINDOW_CANDLES: int = 75
#: User-configurable floor (IConfig key), so a fetch is never smaller than
#: this even with nothing enabled that needs more. Defaults to the render
#: window itself — no extra padding unless the user asks for one.
#: Scoped "CHART_CARD_*", not "DEV_BOARD_*" — this governs ChartCard's own
#: fetch behavior, not anything specific to the Dev Board screen that
#: happens to host it today.
_MIN_FETCH_CANDLES_CONFIG_KEY: str = "CHART_CARD_MIN_FETCH_CANDLES"
_DEFAULT_MIN_FETCH_CANDLES: int = 75

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

# WS status badge (top bar) text/color per FSM state — presentational only,
# derived from the state DashboardPresenter already tracks.
_WS_STATUS_BY_MODE = {
    UIMode.IDLE: ("WS: IDLE", "#848E9C"),
    UIMode.LOCKED: ("WS: SYNCING", "#F3BA2F"),
    UIMode.LIVE: ("WS: LIVE", BULL_COLOR),
    UIMode.ERROR: ("WS: ERROR", BEAR_COLOR),
}


def _tick_to_candle(
    symbol: str,
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
    """
    close_time = datetime.fromtimestamp(close_timestamp, tz=timezone.utc)
    return MarketData(
        symbol=symbol,
        interval=_DEFAULT_INTERVAL_STR,
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
    # Thread-safe Signal Bridges
    # Dùng để truyền dữ liệu từ Background Thread về Main UI Thread
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
        view.set_view_model(self._view_model)

        # Resolve IThreadManager exactly once — stored as an instance attribute.
        # No further container.resolve(IThreadManager) calls anywhere else.
        self._thread_manager: IThreadManager = container.resolve(IThreadManager)

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
        self._active_interval: str = _DEFAULT_INTERVAL_STR

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

        # Must be called explicitly at the end of BasePresenter's contract,
        # and before load_qml() so QML parses against a ready view model.
        self._connect_ui_signals()
        self._connect_engine_events()

        view.load_qml("DevBoardPanel.qml")

        # BOT-034 — auto-start Start Live the moment the Dev Board opens,
        # falling back to Load History if no MarketTickEvent proves a real
        # connection within a few seconds. Constructed last: it immediately
        # calls _on_start_stream(), which needs everything above already set
        # up (script runner, signal connections, FSM).
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
    # BasePresenter contract implementations
    # ================================================================== #

    def _connect_ui_signals(self) -> None:
        """Kết nối các thao tác bấm nút từ ViewModel vào Presenter."""
        view_model = self._view_model
        view_model.loadHistoryRequested.connect(self._on_load_history)
        view_model.startStreamRequested.connect(self._on_start_stream)
        view_model.stopStreamRequested.connect(self._on_stop_stream)

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

    # ================================================================== #
    # FSM Hooks
    # ================================================================== #

    def _on_fsm_error(self) -> None:
        """Auto-recover to IDLE immediately after entering the ERROR state."""
        self.fsm.transition_to(UIMode.IDLE)

    def _on_fsm_state_changed_update_ws_badge(self, old_state, new_state) -> None:
        self._apply_ws_status_badge(new_state)

    def _apply_ws_status_badge(self, mode) -> None:
        text, color = _WS_STATUS_BY_MODE.get(mode, _WS_STATUS_BY_MODE[UIMode.IDLE])
        self._view_model.set_ws_status(text, color)

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
        for card in chart_cards:
            self.active_charts[card.symbol] = card
            # BOT-033 — freshly-created cards only; render_symbol_cards()
            # tears down and rebuilds the old ones on every call, so a
            # connection made here would otherwise accumulate on a widget
            # that no longer exists.
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
        card = self.active_charts.get(_DEFAULT_SYMBOLS[0])
        if card is not None:
            self._script_runner.clear_from_chart(card)
        self._script_runner.rebuild(self._enabled_script_keys())

    def _compute_fetch_limit(self) -> int:
        """
        @brief BOT-034 — how many candles to fetch, as opposed to how many to
        render (_RENDER_WINDOW_CANDLES stays a separate, smaller number).
        @details max(render window, the slowest enabled script's declared
        warm-up requirement, a user-configurable floor). Reads
        `_enabled_script_keys()` fresh (same "read at click time" contract as
        `_rebuild_scripts`) and looks up each key's class in the registry
        without instantiating it — `min_warmup_bars` is a class attribute.
        """
        slowest = max(
            (
                self._script_registry.available()[key].min_warmup_bars
                for key in self._enabled_script_keys()
                if key in self._script_registry.available()
            ),
            default=0,
        )
        floor = self.config.get(
            _MIN_FETCH_CANDLES_CONFIG_KEY, _DEFAULT_MIN_FETCH_CANDLES, cast=int
        )
        return max(_RENDER_WINDOW_CANDLES, slowest, floor)

    # ================================================================== #
    # Qt Slots — execute on the main thread.
    # Long-running work is delegated to dedicated background methods.
    # ================================================================== #

    @Slot()
    @safe_ui_action
    def _on_load_history(self) -> None:
        """
        Lock the UI and submit a background task to load historical klines.
        The blocking DB query loop runs in the background — no UI freeze.
        """
        if self._view_model.historyLoading:
            self._view_model.log_model.append("History load is already in progress.")
            return
        # BOT-034: auto-start's own Start Live workflow (_run_sync_and_start)
        # locks the FSM to LOCKED while it runs and, like _run_load_history,
        # feeds candles through _script_runner from that same background
        # thread. historyLoading alone doesn't cover this case — auto-start
        # never sets it (only _on_load_history does) — so without this guard
        # a Load History click that lands while auto-start is still LOCKED
        # would submit a second background workflow that runs concurrently
        # against the same IndicatorScriptRunner/chart-card state as the
        # first. This was a real, reproduced Windows access violation, not a
        # hypothetical one: two background threads driving the same chart
        # cards at once, previously near-impossible to trigger by hand since
        # nothing used to auto-submit a workflow on Dev Board open.
        if self.fsm.current_state == UIMode.LOCKED:
            self._view_model.log_model.append(
                "Wait for Start Live to finish before loading history."
            )
            return

        self._view_model.set_history_loading(True)
        self._view_model.log_model.append(
            "Loading historical data from local database..."
        )
        symbols = list(_DEFAULT_SYMBOLS)
        self._ensure_chart_cards(symbols)
        self._rebuild_scripts()
        self._thread_manager.submit(
            self._run_load_history,
            symbols,
            self._active_interval,
            self._compute_fetch_limit(),
            self._cancellation_token,
        )

    @Slot()
    @safe_ui_action
    def _on_start_stream(self) -> None:
        """
        Lock the UI and submit the full Auto-Sync → Stream startup workflow
        as a single background task.
        """
        if self._view_model.historyLoading:
            self._view_model.log_model.append(
                "Wait for the current history load before starting live stream."
            )
            return
        # BOT-034: with auto-start, the FSM is LOCKED (or already LIVE)
        # immediately on open — a manual Start Live click during that window
        # used to be unreachable (the app always started IDLE), so this
        # guard never existed. Without it, transition_to(LOCKED) raises
        # InvalidStateTransitionError for anything but IDLE.
        if self.fsm.current_state != UIMode.IDLE:
            self._view_model.log_model.append("Already starting or running — ignoring.")
            return

        self._view_model.log_model.append("Starting Live Stream (Auto-Sync)...")
        self.fsm.transition_to(UIMode.LOCKED)

        symbols = list(_DEFAULT_SYMBOLS)
        interval = TimeFrame(self._active_interval)

        # Prepare chart cards on the main thread (safe: view state only).
        chart_cards = self._ensure_chart_cards(symbols)
        self._rebuild_scripts()
        self._view_model.log_model.append(f"Prepared {len(chart_cards)} charts.")

        self._thread_manager.submit(
            self._run_sync_and_start,
            symbols,
            interval,
            self._active_interval,
            self._compute_fetch_limit(),
            self._cancellation_token,
        )

    @Slot(str)
    @safe_ui_action
    def _on_stream_start_success(self, msg: str) -> None:
        self.ui_log_signal.emit(msg)
        self.fsm.transition_to(UIMode.LIVE)

    @Slot(str)
    @safe_ui_action
    def _on_stream_start_failed(self, msg: str) -> None:
        self.ui_log_signal.emit(f"Stream startup failed: {msg}")
        self.fsm.transition_to(UIMode.ERROR)

    @Slot()
    @safe_ui_action
    def _on_stop_stream(self) -> None:
        self._view_model.log_model.append("Stopping Live Stream...")
        # BOT-034: cancel any in-flight Load History/Start Live background
        # work so it stops touching the chart once the user has explicitly
        # said "stop" — then hand out a fresh token so the *next* Start Live
        # isn't born pre-cancelled (mirrors BinanceWebsocketService minting a
        # new CancellationToken per start_stream() call).
        self._cancellation_token.cancel()
        self._cancellation_token = CancellationToken()
        try:
            cmd = StopLiveStreamCommand()
            self.dispatcher.dispatch(StopLiveStreamCommand, cmd)
            self._view_model.log_model.append("Live Stream stopped.")
            self.fsm.transition_to(UIMode.IDLE)
        except Exception as exc:  # noqa: BLE001 - boundary: report to UI without crashing the presenter
            self._view_model.log_model.append(
                f"Error while stopping: {exc}", level="error"
            )
            self.fsm.transition_to(UIMode.ERROR)

    @Slot(str)
    @safe_ui_action
    def _on_timeframe_changed(self, timeframe: str) -> None:
        """
        @brief BOT-033 — ChartToolbar.sig_timeframe_changed handler.
        @details Unlike the Indicators checkboxes (deliberately no effect
        until the next Load/Start click, see TC-GAP-07), this control lives
        on the chart itself — clicking "5m" reads as "show me 5m now", so it
        reloads immediately: stop-then-restart if a stream is LIVE, otherwise
        a plain reload (skipped if a load is already in flight, same guard
        _on_load_history uses).
        """
        if timeframe == self._active_interval:
            return
        self._active_interval = timeframe

        if self.fsm.current_state == UIMode.LIVE:
            self._on_stop_stream()
            self._on_start_stream()
        elif not self._view_model.historyLoading:
            self._on_load_history()

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
        """HistoryPaginationController's `fetch_older` callback — submits the
        background fetch, same convention as _on_load_history/_on_start_stream
        (dedicated background method, CancellationToken as the last arg)."""
        self._thread_manager.submit(
            self._run_load_more_history,
            symbol,
            self._active_interval,
            oldest_timestamp,
            self.config.get(
                _LOAD_MORE_BATCH_CANDLES_CONFIG_KEY,
                _DEFAULT_LOAD_MORE_BATCH_CANDLES,
                cast=int,
            ),
            self._cancellation_token,
        )

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
        (BOT-032 Phase 6 — none are hardcoded), so this is a pure delegate."""
        card = self.active_charts.get(_DEFAULT_SYMBOLS[0])
        if card is not None:
            self._script_runner.draw(card, name, x_data, y_data)

    @Slot(str, list)
    def _on_script_region_data(self, key: str, spans: list) -> None:
        """Pushes a script's background-tint spans onto the chart."""
        card = self.active_charts.get(_DEFAULT_SYMBOLS[0])
        if card is not None:
            self._script_runner.draw_region(card, key, spans)

    @Slot(str, list)
    def _on_script_info_data(self, key: str, fields: list) -> None:
        """Pushes a script's status-panel fields onto the chart."""
        card = self.active_charts.get(_DEFAULT_SYMBOLS[0])
        if card is not None:
            self._script_runner.draw_info(card, key, fields)

    @Slot(str, list)
    def _on_script_marker_data(self, key: str, markers: list) -> None:
        """Pushes a script's Buy/Sell-style labelled markers onto the chart."""
        card = self.active_charts.get(_DEFAULT_SYMBOLS[0])
        if card is not None:
            self._script_runner.draw_markers(card, key, markers)

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
        # foreign thread is a Qt threading violation.
        self._autostart.on_market_tick()

        is_bullish = c >= o
        price_color = BULL_COLOR if is_bullish else BEAR_COLOR
        self._view_model.set_price_ticker(f"{symbol}  {c:,.2f}", price_color)

        card = self.active_charts.get(symbol)
        if card:
            if is_closed:
                card.append_closed_candle(t, o, h, low, c)
                card.append_closed_volume(t, volume, is_bullish)
                candle = _tick_to_candle(symbol, t, o, h, low, c, volume)
                # BOT-035 — keep the raw-kline cache (used to rebuild+refeed
                # scripts after a later load-more prepend) in sync with what
                # the chart actually shows; otherwise a prepend's rebuild
                # would silently drop every candle that arrived live since
                # the last full Load History/Start Live.
                self._raw_klines_by_symbol.setdefault(symbol, []).append(candle)
                self._script_runner.feed(candle)
            else:
                card.update_last_candle(t, o, h, low, c)
                card.update_last_volume(t, volume, is_bullish)

    # ================================================================== #
    # Background methods — submitted to IThreadManager.
    # MUST NOT touch Qt widgets/models directly. Use signals only.
    # ================================================================== #

    def _run_load_history(
        self,
        symbols: list[str],
        interval_str: str,
        limit: int,
        token: CancellationToken,
    ) -> None:
        """
        @brief Background worker: queries historical klines for each symbol and
        emits results via ui_history_reloaded_signal for safe main-thread rendering.
        @param token Checked before each symbol — set by _on_stop_stream, not
        by navigating away (see DashboardPresenter's _cancellation_token
        docstring). Nothing after a cancelled check touches the chart, so a
        torn-down view is never reached mid-emit.
        """
        try:
            for symbol in symbols:
                if token.is_cancelled():
                    break
                query = GetHistoricalKlinesQuery(
                    symbol=symbol,
                    interval=interval_str,
                    limit=limit,
                    order_by_desc=True,  # Fetch the LATEST N candles from DB
                )
                try:
                    response = self.dispatcher.dispatch(GetHistoricalKlinesQuery, query)
                    klines = getattr(response, "data", response) if response else []

                    if not isinstance(klines, list) or not klines:
                        self.ui_log_signal.emit(
                            f"No historical data found for {symbol}."
                        )
                        continue

                    # Reverse: DB returned newest-first, chart expects oldest-first
                    ordered_klines = list(reversed(klines))
                    mapped_data = self._map_klines(ordered_klines)
                    volume_data = self._map_volume(ordered_klines)
                    self.ui_history_reloaded_signal.emit(
                        symbol, mapped_data, volume_data
                    )
                    self._raw_klines_by_symbol[symbol] = ordered_klines
                    self._script_runner.feed_all(ordered_klines)

                except Exception as exc:  # noqa: BLE001 - boundary: report to UI without crashing the presenter
                    self.ui_log_signal.emit(
                        f"Exception while loading history for {symbol}: {exc}"
                    )
        finally:
            self.ui_history_load_finished_signal.emit()

    def _run_load_more_history(
        self,
        symbol: str,
        interval_str: str,
        before_timestamp: float,
        limit: int,
        token: CancellationToken,
    ) -> None:
        """
        @brief BOT-035 — background worker: fetches up to `limit` candles
        strictly older than `before_timestamp` and emits
        ui_history_prepended_signal for the main thread to prepend.
        @details The repository's `end_time` filter is `open_time <= end_time`
        (inclusive) — passing `before_timestamp` straight through would
        re-return the boundary candle already on the chart. Filtered
        client-side instead, on `close_time` (not `open_time`) to match
        exactly what ChartCard._raw_history's timestamp column already is
        (see _map_klines) — comparing on the same field the chart uses for
        "what do I already have" is what actually guarantees no duplicate,
        regardless of the open_time/close_time gap between them.
        """
        # Whether this run actually found older candles — carried out via the
        # finished signal so HistoryPaginationController knows whether an
        # auto-recheck-after-cooldown could possibly make progress (see its
        # on_load_more_finished docstring). Stays False on every early exit
        # (nothing found, cancelled, or an exception) on purpose.
        found_more = False
        try:
            if token.is_cancelled():
                return
            end_time = datetime.fromtimestamp(before_timestamp, tz=timezone.utc)
            query = GetHistoricalKlinesQuery(
                symbol=symbol,
                interval=interval_str,
                limit=limit,
                end_time=end_time,
                order_by_desc=True,
            )
            response = self.dispatcher.dispatch(GetHistoricalKlinesQuery, query)
            klines = getattr(response, "data", response) if response else []

            if not isinstance(klines, list) or not klines:
                self.ui_log_signal.emit(f"No older data found for {symbol}.")
                return

            ordered_klines = [
                k
                for k in reversed(klines)
                if k.close_time.timestamp() < before_timestamp
            ]
            if not ordered_klines:
                self.ui_log_signal.emit(f"No older data found for {symbol}.")
                return
            if token.is_cancelled():
                return

            self._raw_klines_by_symbol[symbol] = (
                ordered_klines + self._raw_klines_by_symbol.get(symbol, [])
            )
            mapped_data = self._map_klines(ordered_klines)
            volume_data = self._map_volume(ordered_klines)
            self.ui_history_prepended_signal.emit(symbol, mapped_data, volume_data)
            found_more = True

        except Exception as exc:
            self.ui_log_signal.emit(
                f"Exception while loading more history for {symbol}: {exc}"
            )
        finally:
            self.ui_history_prepend_finished_signal.emit(symbol, found_more)

    def _run_sync_and_start(
        self,
        symbols: list[str],
        interval: TimeFrame,
        interval_str: str,
        limit: int,
        token: CancellationToken,
    ) -> None:
        """
        @brief Background worker for the full Auto-Sync → Load History → Start Stream
        workflow. All three steps run sequentially in one background thread.
        Results are communicated back to the UI exclusively via signals.
        @param token Checked between steps and per-symbol — see
        _run_load_history's docstring for the cancellation contract.
        """
        try:
            # Step 1: Auto-Sync (fill any data gaps)
            self.ui_log_signal.emit("Syncing missing data from Binance...")
            sync_cmd = SyncMarketDataCommand(symbols=symbols, interval=interval)
            self.dispatcher.dispatch(SyncMarketDataCommand, sync_cmd)

            if token.is_cancelled():
                return

            # Step 2: Reload historical data onto charts
            self.ui_log_signal.emit("Reloading historical data onto charts...")
            for symbol in symbols:
                if token.is_cancelled():
                    return
                query = GetHistoricalKlinesQuery(
                    symbol=symbol,
                    interval=interval_str,
                    limit=limit,
                    order_by_desc=True,
                )
                response = self.dispatcher.dispatch(GetHistoricalKlinesQuery, query)
                klines = getattr(response, "data", response) if response else []

                if klines and isinstance(klines, list):
                    ordered_klines = list(reversed(klines))
                    mapped_data = self._map_klines(ordered_klines)
                    volume_data = self._map_volume(ordered_klines)
                    self.ui_history_reloaded_signal.emit(
                        symbol, mapped_data, volume_data
                    )
                    self._raw_klines_by_symbol[symbol] = ordered_klines
                    self._script_runner.feed_all(ordered_klines)

            if token.is_cancelled():
                return

            # Step 3: Start the Live WebSocket stream
            self.ui_log_signal.emit("Opening Websocket stream...")
            cmd = StartLiveStreamCommand(symbols=symbols, interval=interval)
            response = self.dispatcher.dispatch(StartLiveStreamCommand, cmd)

            if response and getattr(response, "success", True):
                self.ui_stream_success_signal.emit(
                    f"Live stream for {symbols} is running."
                )
            else:
                msg = getattr(response, "message", "Unknown error")
                self.ui_stream_failed_signal.emit(f"Failed to start: {msg}")

        except Exception as exc:  # noqa: BLE001 - boundary: report to UI without crashing the presenter
            self.ui_stream_failed_signal.emit(f"System error: {exc}")

    @staticmethod
    def _map_klines(klines: list) -> list:
        """
        @brief Converts a list of MarketData entities to the
        (t, o, h, l, c) tuple format expected by FastCandlestickItem.
        Extracted as a static helper to keep _run_* methods readable.
        """
        return [
            (
                float(item.close_time.timestamp()),
                float(item.open_price),
                float(item.high_price),
                float(item.low_price),
                float(item.close_price),
            )
            for item in klines
        ]

    @staticmethod
    def _map_volume(klines: list) -> list:
        """
        @brief Converts a list of MarketData entities to the
        (t, volume, is_bullish) tuple format expected by VolumeItem.
        """
        return [
            (
                float(item.close_time.timestamp()),
                float(item.volume),
                item.close_price >= item.open_price,
            )
            for item in klines
        ]
