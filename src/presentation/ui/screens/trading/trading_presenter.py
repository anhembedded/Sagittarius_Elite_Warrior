from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Signal, Slot
from Sagittarius_Elite_Warrior.src.application.services.equity_curve_recorder import (
    EquityCurveRecorder,
)
from Sagittarius_Elite_Warrior.src.application.services.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.trading.disable_trading import (
    DisableTradingCommand,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.trading.emergency_stop import (
    EmergencyStopCommand,
    EmergencyStopResult,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.trading.enable_trading import (
    EnableTradingBlockReason,
    EnableTradingCommand,
)
from Sagittarius_Elite_Warrior.src.domain.events.equity_sampled_event import (
    EquitySampledEvent,
)
from Sagittarius_Elite_Warrior.src.domain.events.market_tick_event import (
    MarketTickEvent,
)
from Sagittarius_Elite_Warrior.src.domain.events.order_filled_event import (
    OrderFilledEvent,
)
from Sagittarius_Elite_Warrior.src.domain.events.position_changed_event import (
    PositionChangedEvent,
)
from Sagittarius_Elite_Warrior.src.domain.events.position_closed_event import (
    PositionClosedEvent,
)
from Sagittarius_Elite_Warrior.src.domain.trading.live_position import LivePosition
from Sagittarius_Elite_Warrior.src.domain.trading.order import Order
from Sagittarius_Elite_Warrior.src.domain.trading.order_status import OrderStatus
from Sagittarius_Elite_Warrior.src.presentation.ui.common.app_defaults import (
    FALLBACK_INTERVAL,
    FALLBACK_SYMBOL,
    FALLBACK_SYMBOL_OPTIONS,
    default_interval,
    default_symbol,
    default_symbol_options,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.common.equity_feed import EquityFeed
from Sagittarius_Elite_Warrior.src.presentation.ui.common.market_tick_feed import (
    MarketTickFeed,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.common.order_feed import OrderFeed
from Sagittarius_Elite_Warrior.src.presentation.ui.common.order_fill_marker import (
    order_filled_marker,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.OpenOrdersTable.open_order_row import (
    build_open_order_row,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.PositionsTable.positions_row import (
    build_position_row,
)
from sagittarius_engine.extensions.pyside_mvc import BasePresenter, safe_ui_action
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken

from ...common.action_ownership_tracker import ActionOutcome, ActionOwnershipTracker
from .coordinators.chart_coordinator import ChartCoordinator
from .equity_chart_adapter import equity_sample_to_candle, equity_samples_to_candles
from .trading_view_model import TradingViewModel

if TYPE_CHECKING:
    from sagittarius_engine.interfaces.i_container import IContainer

    from .trading_view import TradingView

#: `ActionOwnershipTracker`'s `TKind` — a single action kind (the toggle),
#: same shape as `SettingsPresenter`'s `_CHECK_CONNECTION_ACTION`.
_TOGGLE_ACTION = "toggle_trading"

_BLOCK_REASON_MESSAGES: dict[EnableTradingBlockReason, str] = {
    EnableTradingBlockReason.TRADING_VENUE_DISABLED: (
        "Trading venue đang tắt trong cấu hình — chỉ hỗ trợ Futures Testnet."
    ),
    EnableTradingBlockReason.CONNECTION_NOT_READY: (
        "Kết nối tới sàn chưa sẵn sàng — kiểm tra lại API key/kết nối mạng."
    ),
    EnableTradingBlockReason.UNEXPECTED_POSITIONS: (
        "Tài khoản đang có vị thế mở ngoài dự kiến — vui lòng xử lý thủ công "
        "trên sàn trước khi bật giao dịch."
    ),
}
_UNKNOWN_BLOCK_REASON_MESSAGE = "Không thể bật giao dịch."

#: `ActionOwnershipTracker`'s `TKind` for the Emergency Stop button —
#: tracked on its own `_emergency_stop_tracker` (`BUG-089`), never shared
#: with `_toggle_tracker`: `ActionOwnershipTracker` holds exactly one
#: active action regardless of kind, so sharing one instance meant a
#: toggle click landing while Emergency Stop was still in flight silently
#: fenced Emergency Stop's own result as stale — the failure this button's
#: whole design is built to never allow (see the Emergency Stop section
#: below).
_EMERGENCY_STOP_ACTION = "emergency_stop"

#: `MarkerLayer.set_markers()`'s key for this screen's own live-fill
#: markers (`EPIC-021K` §2.3) — one key, replaced wholesale on every fill
#: for the currently displayed symbol.
_FILL_MARKERS_KEY = "live_fills"

#: Terminal `OrderStatus` values — an order in one of these no longer
#: belongs in the Open Orders table (mirrors `order_status.py`'s own
#: terminal set).
_TERMINAL_ORDER_STATUSES = frozenset(
    {
        OrderStatus.FILLED,
        OrderStatus.CANCELED,
        OrderStatus.REJECTED,
        OrderStatus.EXPIRED,
    }
)


class TradingPresenter(BasePresenter):
    """
    @brief Presenter for the Trading screen (`EPIC-021I`).

    @details Three responsibilities, same split as `DashboardPresenter`/
    `SettingsPresenter`:
    1. The Enable/Disable toggle — a single async action, fenced through
       `ActionOwnershipTracker` exactly like `SettingsPresenter`'s
       connection check (`async-ui-action-rule.md`).
    2. The chart — history load + live ticks, delegated to
       `ChartCoordinator` for the background work; this Presenter owns
       the `CancellationToken` and applies every result to `view.chart`
       on the main thread (`async-ui-action-rule.md` §2 — a Coordinator
       never owns that bookkeeping itself).
    3. Positions/Open Orders tables — kept in two plain dicts here,
       seeded from `EnableTradingResult` on a successful enable and kept
       live via `OrderFeed` (`OrderFilledEvent`/`PositionChangedEvent`),
       the sanctioned single subscriber per `architecture-rule.md` §6.
    4. The equity chart (`EPIC-021M`) — seeded on construction from
       `EquityCurveRecorder`'s backlog (a DI singleton that outlives this
       screen), then appended to live via `EquityFeed`
       (`EquitySampledEvent`), the same single-subscriber shape as #3.

    A position closing to flat is handled by `_on_position_closed`
    (`BUG-086`, `positionClosed` connected in `_connect_engine_events`) —
    `futures_user_data_stream.py` publishes a dedicated `PositionClosedEvent`
    for it, since `PositionChangedEvent` cannot represent "no position"
    (`LivePosition`'s own invariant forbids `position_amt == 0`).

    Emergency Stop is the one path that event can never correct: it stops
    the user-data stream in its own step 1, before steps 2-3 cancel/close
    anything, so nothing will emit further events for whatever those steps
    do. `_on_emergency_stop_completed` refreshes `_positions`/
    `_open_orders` itself from `EmergencyStopResult.final_positions`/
    `final_open_orders` — a best-effort read the handler takes after all
    three steps, regardless of their own outcome (`BUG-093`).
    """

    #: Live tick -> chart, main-thread-safe (`(symbol, close_ts, o, h, l,
    #: c, volume, is_closed)`) — same shape `DashboardPresenter.
    #: ui_chart_update_signal` uses.
    ui_chart_update_signal = Signal(str, float, float, float, float, float, float, bool)
    #: `ChartCoordinator`'s background results, each bound to one `emit_*`
    #: callable passed into its constructor.
    uiHistoryReadySignal = Signal(str, list, list)
    uiLoadFinishedSignal = Signal()
    uiStreamStartedSignal = Signal(str)
    uiStreamFailedSignal = Signal(str)
    uiLogSignal = Signal(str)
    #: `(action_id, EnableTradingResult | None, error_message | None)`.
    enableTradingCompleted = Signal(tuple)
    #: `(action_id, error_message | None)`.
    disableTradingCompleted = Signal(tuple)
    #: `(action_id, EmergencyStopResult | None, error_message | None)`.
    emergencyStopCompleted = Signal(tuple)

    def __init__(self, view: TradingView, container: IContainer) -> None:
        super().__init__(view, container)

        self._thread_manager: IThreadManager = container.resolve(IThreadManager)
        self._session_state: TradingSessionState = container.resolve(
            TradingSessionState
        )
        self._equity_recorder: EquityCurveRecorder = container.resolve(
            EquityCurveRecorder
        )

        config_values = self.config.get_all()
        self._active_symbol = default_symbol(config_values, FALLBACK_SYMBOL)
        self._active_interval = default_interval(config_values, FALLBACK_INTERVAL)

        self._view_model = TradingViewModel()
        self._view_model.set_symbol_options(
            default_symbol_options(config_values, FALLBACK_SYMBOL_OPTIONS)
        )
        self._view_model.symbol = self._active_symbol
        self._view_model.set_trading_state(self._session_state.enabled, False)
        self._view_model.set_session_stats(
            self._session_state.orders_sent_this_session,
            len(self._session_state.known_open_symbols),
        )
        view.set_view_model(self._view_model)

        self.view.chart.set_symbol_title(self._active_symbol)
        self.view.chart.toolbar.set_active(self._active_interval)
        self.view.chart.toolbar.sig_timeframe_changed.connect(
            self._on_timeframe_changed
        )

        self._toggle_tracker: ActionOwnershipTracker[str, None, None] = (
            ActionOwnershipTracker()
        )
        #: `BUG-089` — deliberately a *separate* tracker instance from
        #: `_toggle_tracker`, see `_EMERGENCY_STOP_ACTION`'s own comment.
        self._emergency_stop_tracker: ActionOwnershipTracker[str, None, None] = (
            ActionOwnershipTracker()
        )
        self._positions: dict[str, LivePosition] = {}
        self._open_orders: dict[str, Order] = {}
        #: `EPIC-021K` §2.3 — accumulated live-fill markers, kept per symbol
        #: (not just the active one) so switching back to a symbol later
        #: this session recovers what was already drawn on it, the same
        #: reasoning `TimeframePinPreferences` keeps a store per symbol.
        self._fill_markers_by_symbol: dict[str, list] = {}

        self._cancellation_token = CancellationToken()
        self._shutdown_requested = False
        self._chart_coordinator = ChartCoordinator(
            thread_manager=self._thread_manager,
            dispatcher=self.dispatcher,
            emit_history_ready=self.uiHistoryReadySignal.emit,
            emit_load_finished=self.uiLoadFinishedSignal.emit,
            emit_stream_started=self.uiStreamStartedSignal.emit,
            emit_stream_failed=self.uiStreamFailedSignal.emit,
            emit_log=self.uiLogSignal.emit,
        )

        self._connect_ui_signals()
        self._connect_engine_events()

        # `EPIC-021M`/`BUG-100` — the recorder outlives this screen (a DI
        # singleton written by `FuturesUserDataStream` regardless of
        # whether Trading is even open), so a re-navigation back to this
        # screen recovers the full backlog immediately rather than
        # starting the chart empty. Read *after* `_connect_engine_events()`
        # has already subscribed `_equity_feed`, not before: a live sample
        # recorded in between subscribing and reading is otherwise missed
        # entirely (subscribed-after-read order) rather than merely
        # double-counted — and a double-count from the reverse ordering is
        # itself already harmless, since `ChartCard.append_closed_candle()`
        # replaces the last point in place when its timestamp matches
        # rather than appending a second one.
        self.view.equity_chart.render_historical_data(
            equity_samples_to_candles(self._equity_recorder.samples)
        )

        self._chart_coordinator.start(
            self._active_symbol, self._active_interval, self._cancellation_token
        )

    def shutdown(self) -> None:
        """Cancels this screen's own chart worker. Deliberately does NOT
        call `ChartCoordinator.stop()` — `StopLiveStreamCommand` stops the
        one process-wide stream outright (see that coordinator's own
        docstring), and Dev Board never auto-stops it either; leaving the
        last-started stream running on navigation away matches existing
        behaviour rather than introducing a new one."""
        if self._shutdown_requested:
            return
        self._shutdown_requested = True
        self._cancellation_token.cancel()

    # ================================================================== #
    # BasePresenter contract implementations
    # ================================================================== #

    def _connect_ui_signals(self) -> None:
        self._view_model.symbolChangeRequested.connect(self._on_symbol_change_requested)
        self._view_model.toggleRequested.connect(self._on_toggle_requested)
        self._view_model.emergencyStopRequested.connect(
            self._on_emergency_stop_requested
        )

        self.ui_chart_update_signal.connect(self._on_ui_chart_update)
        self.uiHistoryReadySignal.connect(self._on_history_ready)
        self.uiLoadFinishedSignal.connect(self._on_load_finished)
        self.uiStreamStartedSignal.connect(self._on_stream_started)
        self.uiStreamFailedSignal.connect(self._on_stream_failed)
        self.uiLogSignal.connect(self._append_log)
        self.enableTradingCompleted.connect(self._on_enable_trading_completed)
        self.disableTradingCompleted.connect(self._on_disable_trading_completed)
        self.emergencyStopCompleted.connect(self._on_emergency_stop_completed)

    def _connect_engine_events(self) -> None:
        # `MarketTickEvent` goes through `MarketTickFeed` — one place hears
        # it, many screens display it (`architecture-rule.md` §6). Dev
        # Board is the other subscriber; a raw `self.event_bus.on(...)`
        # here would be the exact duplication
        # `test_one_event_is_not_subscribed_by_two_presenters` exists to
        # catch.
        self._market_tick_feed = MarketTickFeed(self.event_bus, parent=self)
        self._market_tick_feed.marketTick.connect(self._handle_market_tick)
        # `EPIC-021H` — one subscriber, this Presenter, per
        # `architecture-rule.md` §6; the Positions/Open Orders tables are
        # both fed from it.
        self._order_feed = OrderFeed(self.event_bus, parent=self)
        self._order_feed.orderFilled.connect(self._on_order_filled)
        self._order_feed.positionChanged.connect(self._on_position_changed)
        # `BUG-086` — a closed position never reached this table before;
        # without this, "Vị thế đang mở" could keep showing a position the
        # exchange had already closed until the next full reconciliation.
        self._order_feed.positionClosed.connect(self._on_position_closed)
        # `EPIC-021M` — one subscriber, this Presenter, same reasoning as
        # `OrderFeed` above (see `equity_feed.py`'s own docstring).
        self._equity_feed = EquityFeed(self.event_bus, parent=self)
        self._equity_feed.equitySampled.connect(self._on_equity_sampled)

    @Slot(str)
    def _append_log(self, message: str) -> None:
        self._view_model.log_model.append(message, level="info")

    # ================================================================== #
    # Chart symbol/interval — the context bar's own concern, independent
    # of the Enable/Disable toggle (EnableTradingCommand is account-wide).
    # ================================================================== #

    @Slot(str)
    @safe_ui_action
    def _on_symbol_change_requested(self, symbol: str) -> None:
        symbol = symbol.strip().upper()
        if not symbol or symbol == self._active_symbol:
            return
        self._active_symbol = symbol
        self._view_model.symbol = symbol
        self.view.chart.set_symbol_title(symbol)
        self._render_fill_markers()
        self._restart_chart()

    @Slot(str)
    @safe_ui_action
    def _on_timeframe_changed(self, timeframe: str) -> None:
        if timeframe == self._active_interval:
            return
        self._active_interval = timeframe
        self._restart_chart()

    def _restart_chart(self) -> None:
        self._cancellation_token.cancel()
        self._cancellation_token = CancellationToken()
        self._chart_coordinator.stop()
        self._chart_coordinator.start(
            self._active_symbol, self._active_interval, self._cancellation_token
        )

    @Slot(str, list, list)
    def _on_history_ready(self, symbol: str, candles: list, volume: list) -> None:
        if symbol != self._active_symbol:
            return
        self.view.chart.render_historical_data(candles)
        self.view.chart.render_historical_volume(volume)

    @Slot()
    def _on_load_finished(self) -> None:
        """Nothing to unlock — this screen's chart has no loading spinner
        or exclusive-action gate to release (unlike Dev Board's Load
        History/Start Live buttons)."""

    @Slot(str)
    def _on_stream_started(self, message: str) -> None:
        self._append_log(message)

    @Slot(str)
    def _on_stream_failed(self, message: str) -> None:
        self._append_log(f"[ERROR] {message}")

    def _handle_market_tick(self, event: MarketTickEvent) -> None:
        """Reached via `MarketTickFeed`, already marshaled onto the main
        Qt thread — still emits a signal rather than touching `view.chart`
        directly, so this method's own behaviour does not depend on which
        thread reaches it."""
        md = event.market_data
        if md.symbol != self._active_symbol:
            return
        self.ui_chart_update_signal.emit(
            md.symbol,
            md.close_time.timestamp(),
            float(md.open_price),
            float(md.high_price),
            float(md.low_price),
            float(md.close_price),
            float(md.volume),
            md.is_closed,
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
        if symbol != self._active_symbol:
            return
        is_bullish = c >= o
        if is_closed:
            self.view.chart.append_closed_candle(t, o, h, low, c)
            self.view.chart.append_closed_volume(t, volume, is_bullish)
        else:
            self.view.chart.update_last_candle(t, o, h, low, c)
            self.view.chart.update_last_volume(t, volume, is_bullish)

    # ================================================================== #
    # Enable/Disable trading toggle — a single async action, fenced with
    # `ActionOwnershipTracker` (`async-ui-action-rule.md`), same pattern
    # `SettingsPresenter._on_check_connection_requested` uses.
    # ================================================================== #

    @Slot()
    @safe_ui_action
    def _on_toggle_requested(self) -> None:
        # `BUG-089` — the toggle button is already disabled by `busy=True`
        # while Emergency Stop runs (see that section below), but this is
        # the real guard: a click that slips through anyway (a queued Qt
        # event delivered just before the button actually disables) must
        # not begin a new toggle action and, via the shared session state,
        # race the Emergency Stop already in flight.
        if self._emergency_stop_tracker.active_outcome is ActionOutcome.PENDING:
            self._view_model.set_status(
                "Đang dừng khẩn cấp — vui lòng đợi xong trước khi bật/tắt giao dịch.",
                True,
            )
            return
        action = self._toggle_tracker.begin_action(_TOGGLE_ACTION, None, None)
        currently_enabled = self._session_state.enabled
        self._view_model.set_trading_state(currently_enabled, True)
        if currently_enabled:
            self._thread_manager.submit(self._run_disable, action.action_id)
        else:
            self._thread_manager.submit(self._run_enable, action.action_id)

    def _run_enable(self, action_id: int) -> None:
        try:
            result = self.dispatcher.dispatch(
                EnableTradingCommand, EnableTradingCommand()
            )
            self.enableTradingCompleted.emit((action_id, result, None))
        except Exception as exc:  # noqa: BLE001 - worker boundary: report the real failure instead of losing it to a background-thread traceback
            self.enableTradingCompleted.emit((action_id, None, str(exc)))

    def _run_disable(self, action_id: int) -> None:
        try:
            self.dispatcher.dispatch(DisableTradingCommand, DisableTradingCommand())
            self.disableTradingCompleted.emit((action_id, None))
        except Exception as exc:  # noqa: BLE001 - worker boundary
            self.disableTradingCompleted.emit((action_id, str(exc)))

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
            self._view_model.set_trading_state(self._session_state.enabled, False)
            self._view_model.set_status(f"Lỗi khi bật giao dịch: {error}", True)
            return

        self._toggle_tracker.finish_action(action_id, ActionOutcome.SUCCEEDED)
        self._view_model.set_trading_state(result.enabled, False)
        if result.enabled:
            self._view_model.set_status("Đã bật giao dịch.", False)
            # A refusal is the only path that ever returns a non-empty
            # `reconciled_positions` (see `EnableTradingCommandHandler`) —
            # a successful enable therefore always starts with none open.
            self._positions = {}
            self._open_orders = {
                order.client_order_id: order for order in result.reconciled_open_orders
            }
        else:
            message = _BLOCK_REASON_MESSAGES.get(
                result.block_reason, _UNKNOWN_BLOCK_REASON_MESSAGE
            )
            self._view_model.set_status(message, True)
            self._positions = {
                position.symbol: position for position in result.reconciled_positions
            }
            self._open_orders = {
                order.client_order_id: order for order in result.reconciled_open_orders
            }
        self._render_positions()
        self._render_open_orders()
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
            self._view_model.set_trading_state(self._session_state.enabled, False)
            self._view_model.set_status(f"Lỗi khi tắt giao dịch: {error}", True)
            return

        self._toggle_tracker.finish_action(action_id, ActionOutcome.SUCCEEDED)
        self._view_model.set_trading_state(False, False)
        self._view_model.set_status("Đã tắt giao dịch.", False)

    # ================================================================== #
    # Emergency Stop (`EPIC-021K` §2.2) — deliberately NOT `@safe_ui_action`
    # (that decorator swallows exceptions; this button's whole point is
    # that a failure must be seen, never silently dropped mid-flow —
    # ONBOARDING.md §8, bẫy 8). The manual `try/except` below reports every
    # failure through the ViewModel instead, the same "worker boundary"
    # idiom `_run_enable`/`_run_disable` already use for their own
    # background halves.
    # ================================================================== #

    @Slot()
    def _on_emergency_stop_requested(self) -> None:
        try:
            # `BUG-089` debounce — the Emergency Stop button is
            # deliberately never disabled (it must always be clickable),
            # so a second click while one is still in flight is only
            # caught here: without this, it would submit a second,
            # independent `EmergencyStopCommand` against the live exchange
            # racing the first one's own cancel/close calls.
            if self._emergency_stop_tracker.active_outcome is ActionOutcome.PENDING:
                self._view_model.set_status(
                    "Đang dừng khẩn cấp — yêu cầu đã được gửi, vui lòng đợi.", False
                )
                return
            action = self._emergency_stop_tracker.begin_action(
                _EMERGENCY_STOP_ACTION, None, None
            )
            # Disables the toggle button for the duration (`_apply_trading_
            # state`) — Enable/Disable must not race Emergency Stop's own
            # `disable()`/`place_order()` calls.
            self._view_model.set_trading_state(self._session_state.enabled, True)
            self._view_model.set_status("Đang dừng khẩn cấp...", False)
            self._thread_manager.submit(self._run_emergency_stop, action.action_id)
        except Exception as exc:  # noqa: BLE001 - deliberately not @safe_ui_action, see this section's own docstring
            self._view_model.set_trading_state(self._session_state.enabled, False)
            self._view_model.set_status(f"Lỗi khi dừng khẩn cấp: {exc}", True)

    def _run_emergency_stop(self, action_id: int) -> None:
        try:
            result = self.dispatcher.dispatch(
                EmergencyStopCommand, EmergencyStopCommand()
            )
            self.emergencyStopCompleted.emit((action_id, result, None))
        except Exception as exc:  # noqa: BLE001 - worker boundary
            self.emergencyStopCompleted.emit((action_id, None, str(exc)))

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
            self._view_model.set_trading_state(self._session_state.enabled, False)
            self._view_model.set_status(f"Lỗi khi dừng khẩn cấp: {error}", True)
            self._append_log(f"[ERROR] Dừng khẩn cấp thất bại: {error}")
            return

        self._emergency_stop_tracker.finish_action(
            action_id,
            ActionOutcome.SUCCEEDED if result.fully_succeeded else ActionOutcome.FAILED,
        )
        self._view_model.set_trading_state(self._session_state.enabled, False)
        self._log_emergency_stop_result(result)
        self._apply_emergency_stop_final_state(result)
        if result.fully_succeeded:
            self._view_model.set_status("Đã dừng khẩn cấp.", False)
        else:
            self._view_model.set_status(
                "DỪNG KHẨN CẤP — THẤT BẠI MỘT PHẦN. Xem nhật ký.", True
            )

    def _apply_emergency_stop_final_state(self, result: EmergencyStopResult) -> None:
        """`BUG-093` — the user-data stream is already stopped by
        Emergency Stop's own step 1, so `_on_order_filled`/
        `_on_position_changed`/`_on_position_closed` will never fire for
        whatever steps 2-3 actually did. Without this, the Positions/Open
        Orders tables keep showing whatever they held right before the
        button was pressed — stale, and on a full success, actively wrong
        (still "open" for a position that is now flat)."""
        if not result.final_state_confirmed:
            self._append_log(
                "[WARNING] Không thể xác nhận trạng thái tài khoản sau khi dừng "
                "khẩn cấp — bảng vị thế/lệnh chờ bên dưới có thể không còn đúng. "
                "Chạy `exchange-status` để kiểm tra trực tiếp."
            )
            return
        self._positions = {
            position.symbol: position for position in result.final_positions
        }
        self._open_orders = {
            order.client_order_id: order for order in result.final_open_orders
        }
        self._render_positions()
        self._render_open_orders()

    def _log_emergency_stop_result(self, result: EmergencyStopResult) -> None:
        self._append_log("DỪNG KHẨN CẤP")
        for index, (label, step) in enumerate(
            (
                ("Tắt giao dịch", result.trading_disabled),
                ("Huỷ lệnh chờ", result.orders_cancelled),
                ("Đóng vị thế", result.positions_closed),
            ),
            start=1,
        ):
            mark = "✔" if step.succeeded else "✘"
            self._append_log(f"  {index}. {label} ... {mark} {step.detail}")

    # ================================================================== #
    # Positions/Open Orders tables — seeded above, kept live here.
    # ================================================================== #

    def _on_order_filled(self, event: OrderFilledEvent) -> None:
        order = event.order
        if order.status in _TERMINAL_ORDER_STATUSES:
            self._open_orders.pop(order.client_order_id, None)
        else:
            self._open_orders[order.client_order_id] = order
        self._render_open_orders()
        self._refresh_session_stats()
        self._record_fill_marker(event)

    def _on_position_changed(self, event: PositionChangedEvent) -> None:
        self._positions[event.position.symbol] = event.position
        self._render_positions()

    def _on_position_closed(self, event: PositionClosedEvent) -> None:
        """`BUG-086` — removes a position the exchange reports as flat.
        `dict.pop(..., None)` rather than indexing: this event fires for
        every symbol going flat, including one this table never held (no
        prior `PositionChangedEvent` for it this session)."""
        self._positions.pop(event.symbol, None)
        self._render_positions()

    def _render_positions(self) -> None:
        self.view.set_positions(
            [build_position_row(position) for position in self._positions.values()]
        )

    def _render_open_orders(self) -> None:
        self.view.set_open_orders(
            [build_open_order_row(order) for order in self._open_orders.values()]
        )

    def _refresh_session_stats(self) -> None:
        self._view_model.set_session_stats(
            self._session_state.orders_sent_this_session,
            len(self._session_state.known_open_symbols),
        )

    # ================================================================== #
    # Live fill markers (`EPIC-021K` §2.3) — chart-only, per symbol; never
    # shown for a symbol other than whatever `view.chart` currently displays.
    # ================================================================== #

    def _record_fill_marker(self, event: OrderFilledEvent) -> None:
        symbol = event.order.symbol
        self._fill_markers_by_symbol.setdefault(symbol, []).append(
            order_filled_marker(event)
        )
        if symbol == self._active_symbol:
            self._render_fill_markers()

    def _render_fill_markers(self) -> None:
        self.view.chart.set_script_markers(
            _FILL_MARKERS_KEY,
            self._fill_markers_by_symbol.get(self._active_symbol, []),
        )

    # ================================================================== #
    # Live equity chart (`EPIC-021M`) — one point per `ACCOUNT_UPDATE` that
    # carries a balance, account-wide (no per-symbol filtering, unlike the
    # fill markers above).
    # ================================================================== #

    def _on_equity_sampled(self, event: EquitySampledEvent) -> None:
        """`EquityFeed.equitySampled` handler — already on the main thread."""
        self.view.equity_chart.append_closed_candle(
            *equity_sample_to_candle(event.sample)
        )
