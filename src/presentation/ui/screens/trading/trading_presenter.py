from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Signal, Slot
from Sagittarius_Elite_Warrior.src.application.services.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.trading.disable_trading import (
    DisableTradingCommand,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.trading.enable_trading import (
    EnableTradingBlockReason,
    EnableTradingCommand,
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
from Sagittarius_Elite_Warrior.src.presentation.ui.common.market_tick_feed import (
    MarketTickFeed,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.common.order_feed import OrderFeed
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

    **Known gap, not fixed here** (see `EPIC-021I`'s own task write-up):
    `futures_user_data_stream.py::_handle_account_update()` does not
    publish a `PositionChangedEvent` when a position closes to flat —
    only when it changes to a still-open state. This screen's Positions
    table can therefore go stale (show a position that has actually
    closed) until the next successful `EnableTradingCommand`
    re-reconciles it. Fixing the publisher is out of scope for this
    build; documented as a follow-up, not worked around with a new
    polling mechanism this screen has no mandate to add.
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

    def __init__(self, view: TradingView, container: IContainer) -> None:
        super().__init__(view, container)

        self._thread_manager: IThreadManager = container.resolve(IThreadManager)
        self._session_state: TradingSessionState = container.resolve(
            TradingSessionState
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
        self._positions: dict[str, LivePosition] = {}
        self._open_orders: dict[str, Order] = {}

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

        self.ui_chart_update_signal.connect(self._on_ui_chart_update)
        self.uiHistoryReadySignal.connect(self._on_history_ready)
        self.uiLoadFinishedSignal.connect(self._on_load_finished)
        self.uiStreamStartedSignal.connect(self._on_stream_started)
        self.uiStreamFailedSignal.connect(self._on_stream_failed)
        self.uiLogSignal.connect(self._append_log)
        self.enableTradingCompleted.connect(self._on_enable_trading_completed)
        self.disableTradingCompleted.connect(self._on_disable_trading_completed)

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

    def _on_position_changed(self, event: PositionChangedEvent) -> None:
        self._positions[event.position.symbol] = event.position
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
