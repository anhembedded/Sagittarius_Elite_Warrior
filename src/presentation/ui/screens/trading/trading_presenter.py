from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Signal, Slot
from Sagittarius_Elite_Warrior.src.application.services.live_strategy_session import (
    LiveStrategySession,
)
from Sagittarius_Elite_Warrior.src.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.live_strategy_config import (
    SUPPORTED_LIVE_INTERVALS,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.market_tick_event import (
    MarketTickEvent,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_historical_klines import (
    IHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sync import (
    IMarketDataSync,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_stream import (
    IMarketStream,
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_equity_curve import (
    IEquityCurve,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_order_submission import (
    IOrderSubmission,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_session import (
    ITradingSession,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.common.equity_chart_adapter import (
    equity_sample_to_candle,
    equity_samples_to_candles,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.common.equity_feed import EquityFeed
from Sagittarius_Elite_Warrior.src.presentation.ui.common.execute_order_block_reason import (
    format_execute_order_block_reason,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.common.live_order_book_coordinator import (
    LiveOrderBookCoordinator,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.common.market_tick_feed import (
    MarketTickFeed,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.common.order_feed import OrderFeed
from Sagittarius_Elite_Warrior.src.presentation.ui.common.order_fill_marker import (
    order_filled_marker,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.common.signal_feed import SignalFeed
from Sagittarius_Elite_Warrior.src.presentation.ui.common.strategy_arming_coordinator import (
    StrategyArmingCoordinator,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.action_ownership_tracker import (
    ActionOutcome,
    ActionOwnershipTracker,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.app_defaults import (
    FALLBACK_INTERVAL,
    FALLBACK_SYMBOL,
    FALLBACK_SYMBOL_OPTIONS,
    default_interval,
    default_symbol,
    default_symbol_options,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.enum_labels import EnumLabels
from sagittarius_engine.extensions.pyside_mvc import BasePresenter, safe_ui_action
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken

from .coordinators.chart_coordinator import ChartCoordinator
from .coordinators.strategy_overlay_coordinator import (
    StrategyOverlayCoordinator,
)
from .trading_view_model import TradingViewModel

if TYPE_CHECKING:
    from sagittarius_engine.interfaces.i_container import IContainer

    from .trading_view import TradingView

#: `ActionOwnershipTracker`'s `TKind` — a single action kind (the toggle),
#: same shape as `SettingsPresenter`'s `_CHECK_CONNECTION_ACTION`.
#: `BUG-107` — opening the Trading screen must not open a network
#: connection. Same rule, same default and the same reason as Dev Board's
#: `DEV_BOARD_AUTOSTART_ENABLED` (`BOT-062`: "opening the screen must not
#: silently start a live connection unless the user has opted in"); this
#: screen was simply never held to it, because `EPIC-021I` designed it as
#: "being open means live" back when it had no other way to get prices.
#:
#: Off by default: the chart still fills from the local database on open,
#: and goes live the moment the user enables trading — which is an explicit
#: request for live prices, unlike clicking a sidebar item.
_CHART_AUTOSTART_CONFIG_KEY: str = "TRADING_CHART_AUTOSTART_ENABLED"
_DEFAULT_CHART_AUTOSTART_ENABLED: bool = False

_TOGGLE_ACTION = "toggle_trading"
#: `EPIC-022D` — its own `ActionOwnershipTracker` slot, for the same
#: reason `BUG-089` gave Emergency Stop one: a tracker holds exactly one
#: active action regardless of kind, so sharing an instance would let an
#: arm click landing mid-toggle fence the toggle's own result as stale.
_ARM_ACTION = "arm_strategy"
#: What the interval combo offers comes from the domain
#: (`SUPPORTED_LIVE_INTERVALS`), not from a list typed here (`BOT-125`
#: review). `LiveStrategyConfig` rejects anything outside it, so a
#: separate UI list could only ever drift into offering a value that
#: arming would then refuse.

#: `EnumLabels`, not a bare dict: the table was already missing
#: `SUPERSEDED_BY_CONCURRENT_STATE_CHANGE`, and the `.get(..., generic)`
#: below hid that — the one refusal a user most needs explained (an
#: Emergency Stop landing mid-enable, `BUG-088`) read as "Không thể bật
#: giao dịch." Construction now refuses an incomplete table at import.
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
       `IEquityCurve`'s backlog (a DI singleton that outlives this
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
    uiHistoryReadySignal = Signal(str, list, list, list)
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
    #: `EPIC-024B` §0 — per-order cancel, same shape Dev Board's identical
    #: signal uses. `(symbol, client_order_id, CancelOrderResult | None,
    #: error_message | None)`.
    cancelOrderCompleted = Signal(tuple)

    def __init__(self, view: TradingView, container: IContainer) -> None:
        super().__init__(view, container)

        self._thread_manager: IThreadManager = container.resolve(IThreadManager)
        self._trading_session: ITradingSession = container.resolve(ITradingSession)
        self._order_submission: IOrderSubmission = container.resolve(IOrderSubmission)
        self._equity_curve: IEquityCurve = container.resolve(IEquityCurve)

        config_values = self.config.get_all()
        self._active_symbol = default_symbol(config_values, FALLBACK_SYMBOL)
        self._active_interval = default_interval(config_values, FALLBACK_INTERVAL)

        self._view_model = TradingViewModel()
        self._view_model.set_symbol_options(
            default_symbol_options(config_values, FALLBACK_SYMBOL_OPTIONS)
        )
        self._view_model.symbol = self._active_symbol
        # One snapshot, not three reads: `TradingSessionSnapshot` exists so a
        # screen cannot observe half of a change the websocket thread is
        # making (`ITradingSession`'s own docstring — five files used to read
        # the mutable state directly while `reconcile_position()` rewrote it).
        session = self._trading_session.snapshot()
        self._view_model.set_trading_state(session.enabled, False)
        self._view_model.set_session_stats(
            session.orders_sent_this_session,
            len(session.known_open_symbols),
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
        #: `EPIC-023A` follow-up — pulled out of this Presenter once Dev
        #: Board needed the identical Positions/Open Orders bookkeeping
        #: (`live_order_book_coordinator.py`'s own docstring has the story).
        self._order_book = LiveOrderBookCoordinator(
            view=self.view, emit_log=self._append_log
        )
        #: `EPIC-021K` §2.3 — accumulated live-fill markers, kept per symbol
        #: (not just the active one) so switching back to a symbol later
        #: this session recovers what was already drawn on it, the same
        #: reasoning `TimeframePinPreferences` keeps a store per symbol.
        self._fill_markers_by_symbol: dict[str, list] = {}

        self._cancellation_token = CancellationToken()
        self._shutdown_requested = False
        self._chart_coordinator = ChartCoordinator(
            thread_manager=self._thread_manager,
            # `EPIC-025` PR 0.5: resolved here and injected, like every other
            # dependency this Presenter owns — a Coordinator must not reach
            # into the container itself (`async-ui-action-rule.md`).
            market_data_sync=container.resolve(IMarketDataSync),
            historical_klines=container.resolve(IHistoricalKlines),
            market_stream=container.resolve(IMarketStream),
            emit_history_ready=self.uiHistoryReadySignal.emit,
            emit_load_finished=self.uiLoadFinishedSignal.emit,
            emit_stream_started=self.uiStreamStartedSignal.emit,
            emit_stream_failed=self.uiStreamFailedSignal.emit,
            emit_log=self.uiLogSignal.emit,
        )

        # `EPIC-022D` — the strategy card. Constructed before
        # `_connect_ui_signals()` so its signals have something to reach,
        # and restored (`EPIC-022F`) before the chart starts, so the card
        # is never briefly blank on a screen that already knows what the
        # user picked last session.
        self._strategy_session: LiveStrategySession = container.resolve(
            LiveStrategySession
        )
        self._arm_tracker: ActionOwnershipTracker[str, None, None] = (
            ActionOwnershipTracker()
        )
        self._overlay_coordinator = StrategyOverlayCoordinator(
            get_chart=lambda: self.view.chart,
            available_strategies=lambda: container.resolve(
                StrategyRegistry
            ).available(),
        )
        self._arming_coordinator = StrategyArmingCoordinator(
            view_model=self._view_model,
            config=self.config,
            dispatcher=self.dispatcher,
            available_strategies=lambda: container.resolve(
                StrategyRegistry
            ).available(),
            get_active_symbol=lambda: self._active_symbol,
            get_armed_config=lambda: self._strategy_session.config,
            tracker=self._arm_tracker,
            arm_action_kind=_ARM_ACTION,
            set_status=self._view_model.set_status,
            append_log=self._append_log,
            on_armed_changed=self._on_armed_config_changed,
        )
        self._arming_coordinator.restore_into_view_model(list(SUPPORTED_LIVE_INTERVALS))
        self._refresh_armed_summary(busy=False)
        # Boot may already have armed a strategy from config
        # (`_arm_from_config`), so the overlay starts from the session's
        # truth rather than assuming nothing is armed.
        self._overlay_coordinator.set_armed_config(self._strategy_session.config)

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
            equity_samples_to_candles(self._equity_curve.samples())
        )

        # `BUG-107` — history from the local database always; the network
        # (Binance sync + websocket) only when the user has opted in.
        self._chart_live_requested = bool(
            self.config.get(
                _CHART_AUTOSTART_CONFIG_KEY,
                _DEFAULT_CHART_AUTOSTART_ENABLED,
                cast=bool,
            )
        )
        self._chart_coordinator.start(
            self._active_symbol,
            self._active_interval,
            self._cancellation_token,
            go_live=self._chart_live_requested,
        )

    def shutdown(self) -> None:
        """Cancels this screen's own chart worker. Deliberately does NOT
        call `ChartCoordinator.stop()` — not because it would be unsafe
        (`BOT-126` made `stop()` owner-scoped, so it would only ever release
        this screen's own subscription), but because Dev Board never
        auto-stops on navigation away either; leaving the last-started
        stream running matches that existing UX choice rather than
        introducing a new one."""
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
        self._view_model.armRequested.connect(self._on_arm_requested)
        self._view_model.disarmRequested.connect(self._on_disarm_requested)
        self._view_model.botParamsSaveRequested.connect(
            self._on_bot_params_save_requested
        )
        self._view_model.strategyConfigChanged.connect(
            self._on_strategy_selection_changed
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

        # `EPIC-024B` §0 — per-order cancel (Open Orders table's "Huỷ").
        self.view.cancelOrderRequested.connect(self._on_cancel_order_requested)
        self.cancelOrderCompleted.connect(self._on_cancel_order_completed)

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
        # `BUG-084` — otherwise a signal-driven order blocked by sizing or a
        # trading limit is invisible: no table changes, no exception, just
        # a screen that sits still whether or not the strategy ever fired.
        self._order_feed.orderBlocked.connect(self._on_order_blocked)
        # `EPIC-021M` — one subscriber, this Presenter, same reasoning as
        # `OrderFeed` above (see `equity_feed.py`'s own docstring).
        self._equity_feed = EquityFeed(self.event_bus, parent=self)
        # `EPIC-022E` — `SignalGeneratedEvent` has been published since
        # `BOT-020` with nothing in the UI listening.
        self._signal_feed = SignalFeed(self.event_bus, parent=self)
        self._signal_feed.signalGenerated.connect(self._on_signal_generated)
        self._equity_feed.equitySampled.connect(self._on_equity_sampled)

    @Slot(str)
    def _append_log(self, message: str) -> None:
        self._view_model.log_model.append(message, level="info")

    # ================================================================== #
    # Chart symbol/interval — the context bar's own concern, independent
    # of the Enable/Disable toggle (`ITradingSession.enable()` is account-wide).
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

    def _go_live_if_not_already(self) -> None:
        """Promotes the chart from local-history-only to live, once.

        @details Deliberately does NOT go through `_restart_chart()`'s
        stop-then-start: there is no stream of this screen's own to stop
        yet (it has only ever read local history), so a `stop()` here would
        release nothing of this screen's own — `BOT-126` made
        `ChartCoordinator.stop()` owner-scoped, so calling it early would
        be a harmless no-op rather than a risk, but it is still skipped as
        dead motion — the original always-live open path never called
        `stop()` first either.
        """
        if self._chart_live_requested:
            return
        self._chart_live_requested = True
        self._cancellation_token.cancel()
        self._cancellation_token = CancellationToken()
        self._chart_coordinator.start(
            self._active_symbol,
            self._active_interval,
            self._cancellation_token,
            go_live=True,
        )

    def _restart_chart(self) -> None:
        """Symbol/interval change: reload the chart for the new selection.

        @details `stop()` runs first only when this screen is itself the
        live one — same reasoning as `_go_live_if_not_already()`: this
        screen must only ever stop a stream it started.
        """
        self._cancellation_token.cancel()
        self._cancellation_token = CancellationToken()
        if self._chart_live_requested:
            self._chart_coordinator.stop()
        self._chart_coordinator.start(
            self._active_symbol,
            self._active_interval,
            self._cancellation_token,
            go_live=self._chart_live_requested,
        )

    @Slot(str, list, list)
    def _on_history_ready(
        self, symbol: str, candles: list, volume: list, klines: list
    ) -> None:
        if symbol != self._active_symbol:
            return
        self.view.chart.render_historical_data(candles)
        self.view.chart.render_historical_volume(volume)
        # `EPIC-022E` — the strategy's own lines are drawn from the same
        # history the candles came from, so they appear together rather
        # than a redraw later.
        self._overlay_coordinator.set_history(klines)

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
        # `BOT-126` — same fault `BUG-085` fixed for `MarketTickEventHandler`,
        # never applied here: a stream now genuinely can carry more than one
        # interval for the same symbol at once (Dev Board and this screen
        # each own their own subscription), so filtering by symbol alone
        # would let another screen's interval feed this screen's chart.
        if md.interval != self._active_interval:
            return
        # `EPIC-022E` — closed candles only. A strategy's readings advance
        # on bar close and nowhere else, so redrawing per in-progress tick
        # would replay the whole buffer to draw an unchanged value.
        if md.is_closed:
            self._overlay_coordinator.on_closed_candle(md)
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
                "Emergency stop in progress — please wait for it to finish "
                "before enabling/disabling trading.",
                True,
            )
            return
        action = self._toggle_tracker.begin_action(_TOGGLE_ACTION, None, None)
        currently_enabled = self._trading_session.snapshot().enabled
        self._view_model.set_trading_state(currently_enabled, True)
        if currently_enabled:
            self._thread_manager.submit(self._run_disable, action.action_id)
        else:
            self._thread_manager.submit(self._run_enable, action.action_id)

    def _run_enable(self, action_id: int) -> None:
        try:
            result = self._trading_session.enable()
            self.enableTradingCompleted.emit((action_id, result, None))
        except Exception as exc:  # noqa: BLE001 - worker boundary: report the real failure instead of losing it to a background-thread traceback
            self.enableTradingCompleted.emit((action_id, None, str(exc)))

    def _run_disable(self, action_id: int) -> None:
        try:
            self._trading_session.disable()
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
            self._view_model.set_trading_state(
                self._trading_session.snapshot().enabled, False
            )
            self._view_model.set_status(f"Error enabling trading: {error}", True)
            return

        self._toggle_tracker.finish_action(action_id, ActionOutcome.SUCCEEDED)
        self._view_model.set_trading_state(result.enabled, False)
        if result.enabled:
            self._view_model.set_status("Trading enabled.", False)
            # `BUG-107` — THIS is the explicit request for live prices, not
            # the sidebar click that opened the screen. Trading without them
            # would be trading blind, so the chart goes live here and stays
            # live for the rest of the session (turning trading back off does
            # not stop it: the stream is process-wide and Dev Board may be
            # relying on it — the same constraint `shutdown()` documents).
            self._go_live_if_not_already()
            # A refusal is the only path that ever returns a non-empty
            # `reconciled_positions` (see `ITradingSession.enable()`) —
            # a successful enable therefore always starts with none open.
            self._order_book.replace_all(
                positions=[], open_orders=result.reconciled_open_orders
            )
        else:
            self._view_model.set_status(
                _BLOCK_REASON_MESSAGES[result.block_reason], True
            )
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
            self._view_model.set_status(f"Error disabling trading: {error}", True)
            return

        self._toggle_tracker.finish_action(action_id, ActionOutcome.SUCCEEDED)
        self._view_model.set_trading_state(False, False)
        self._view_model.set_status("Trading disabled.", False)

    # ================================================================== #
    # Strategy card (`EPIC-022D`) — the button handlers live in
    # `StrategyArmingCoordinator`; what stays here is what the Presenter
    # genuinely owns: the ViewModel slots Qt connects to, and the signal
    # feed (which is a screen-wide subscription, not part of the card).
    # ================================================================== #

    @Slot()
    def _on_strategy_selection_changed(self) -> None:
        self._arming_coordinator.on_strategy_selection_changed()

    @Slot("QVariantMap")
    @safe_ui_action
    def _on_bot_params_save_requested(self, values: dict) -> None:
        if self._arming_coordinator.apply_params(values):
            self._view_model.set_status("Strategy Parameters saved.", False)

    @Slot()
    def _on_arm_requested(self) -> None:
        self._arming_coordinator.on_arm_clicked()

    @Slot()
    def _on_disarm_requested(self) -> None:
        self._arming_coordinator.on_disarm_clicked()

    def _on_armed_config_changed(self, config, busy: bool) -> None:
        """Called by the Coordinator whenever what is armed may have
        changed — keeps the summary line and the chart overlay in step
        from one place instead of each caller remembering both."""
        self._view_model.set_armed_summary(
            self._arming_coordinator.armed_summary(config), busy
        )
        self._overlay_coordinator.set_armed_config(config)

    def _refresh_armed_summary(self, *, busy: bool) -> None:
        self._on_armed_config_changed(self._strategy_session.config, busy)

    def _on_signal_generated(self, event) -> None:
        """Shows the strategy's latest decision, in its own words.

        @details Filtered to the armed symbol on purpose: this event also
        carries signals from a *backtest* `StrategyEngine` running on the
        same shared bus (see `SignalFeed`'s docstring), and a card
        labelled "TÍN HIỆU GẦN NHẤT" on the live trading screen showing a
        backtest's output would be exactly the kind of half-true UI this
        epic set out to remove.
        """
        signal = getattr(event, "signal", None)
        if signal is None:
            return
        config = self._strategy_session.config
        if config is None or signal.symbol != config.symbol:
            return
        action = getattr(signal.action, "value", str(signal.action))
        when = signal.time.strftime("%H:%M:%S")
        self._view_model.set_last_signal_text(
            f"{when} · {action} @ {signal.price:g} — {signal.reason}"
        )

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
            # independent `ITradingSession.emergency_stop()` against the
            # live exchange, racing the first one's own cancel/close calls.
            if self._emergency_stop_tracker.active_outcome is ActionOutcome.PENDING:
                self._view_model.set_status(
                    "Emergency stop in progress — the request has already been sent, please wait.",
                    False,
                )
                return
            action = self._emergency_stop_tracker.begin_action(
                _EMERGENCY_STOP_ACTION, None, None
            )
            # Disables the toggle button for the duration (`_apply_trading_
            # state`) — Enable/Disable must not race Emergency Stop's own
            # `disable()`/`place_order()` calls.
            self._view_model.set_trading_state(
                self._trading_session.snapshot().enabled, True
            )
            self._view_model.set_status("Emergency stop in progress...", False)
            self._thread_manager.submit(self._run_emergency_stop, action.action_id)
        except Exception as exc:  # noqa: BLE001 - deliberately not @safe_ui_action, see this section's own docstring
            self._view_model.set_trading_state(
                self._trading_session.snapshot().enabled, False
            )
            self._view_model.set_status(f"Error during emergency stop: {exc}", True)

    def _run_emergency_stop(self, action_id: int) -> None:
        try:
            result = self._trading_session.emergency_stop()
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
            self._view_model.set_trading_state(
                self._trading_session.snapshot().enabled, False
            )
            self._view_model.set_status(f"Error during emergency stop: {error}", True)
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
            self._view_model.set_status("Emergency stop completed.", False)
        else:
            self._view_model.set_status(
                "EMERGENCY STOP — PARTIALLY FAILED. See the log.", True
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
    # Positions/Open Orders tables — bookkeeping delegated to
    # `LiveOrderBookCoordinator` (`EPIC-023A` follow-up); what stays here is
    # what is genuinely screen-specific (session stats, the fill marker).
    # ================================================================== #

    def _on_order_filled(self, event: OrderFilledEvent) -> None:
        self._order_book.on_order_filled(event.order)
        self._refresh_session_stats()
        self._record_fill_marker(event)

    def _on_position_changed(self, event: PositionChangedEvent) -> None:
        self._order_book.on_position_changed(event.position)

    def _on_position_closed(self, event: PositionClosedEvent) -> None:
        """`BUG-086` — removes a position the exchange reports as flat."""
        self._order_book.on_position_closed(event.symbol)

    def _on_order_blocked(self, event: LiveOrderBlockedEvent) -> None:
        """`BUG-084` — the one place a blocked signal-driven order becomes
        visible on the Trading screen itself, not just in a log file an
        operator isn't watching."""
        self._order_book.on_order_blocked(event.symbol, event.reason)

    def _refresh_session_stats(self) -> None:
        session = self._trading_session.snapshot()
        self._view_model.set_session_stats(
            session.orders_sent_this_session,
            len(session.known_open_symbols),
        )

    # ================================================================== #
    # Per-order cancel (`EPIC-024B` §0) — the Open Orders table's "Huỷ"
    # button, shared with Dev Board (`OpenOrdersTable`/`OpenOrdersPanel`
    # are the same component both screens embed). No `ActionOwnershipTracker`
    # — see `DashboardPresenter`'s identical block for why.
    # ================================================================== #

    @Slot(str, str)
    @safe_ui_action
    def _on_cancel_order_requested(self, symbol: str, client_order_id: str) -> None:
        self._append_log(f"Cancelling order {client_order_id} ({symbol})...")
        self._thread_manager.submit(self._run_cancel_order, symbol, client_order_id)

    def _run_cancel_order(self, symbol: str, client_order_id: str) -> None:
        try:
            result = self._order_submission.cancel(symbol, client_order_id)
            self.cancelOrderCompleted.emit((symbol, client_order_id, result, None))
        except Exception as exc:  # noqa: BLE001 - worker boundary
            self.cancelOrderCompleted.emit((symbol, client_order_id, None, str(exc)))

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
