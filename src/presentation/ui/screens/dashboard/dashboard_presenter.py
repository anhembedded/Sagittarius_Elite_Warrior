from __future__ import annotations

from typing import TYPE_CHECKING, List, Tuple

from PySide6.QtCore import Signal, Slot

from sagittarius_engine.extensions.pyside_mvc import BasePresenter, safe_ui_action
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

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
from Binace_Bot.src.domain.events.market_tick_event import MarketTickEvent
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame
from Binace_Bot.src.presentation.ui.constants import UIMode

if TYPE_CHECKING:
    from sagittarius_engine.interfaces.i_container import IContainer

    from Binace_Bot.src.presentation.ui.screens.dashboard.dashboard_view import (
        DashboardView,
    )

# ---------------------------------------------------------------------------
# Constants — no magic values scattered in method bodies
# ---------------------------------------------------------------------------
_DEFAULT_SYMBOLS: Tuple[str, ...] = ("BTCUSDT", "ETHUSDT")
_DEFAULT_INTERVAL_STR: str = "1m"
_DEFAULT_KLINE_LIMIT: int = 5000


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
    """

    # ------------------------------------------------------------------ #
    # Thread-safe Signal Bridges
    # Dùng để truyền dữ liệu từ Background Thread về Main UI Thread
    # ------------------------------------------------------------------ #
    ui_log_signal = Signal(str)
    ui_chart_update_signal = Signal(str, float, float, float, float, float, bool)

    # Dedicated signals for the Auto-Sync Workflow
    ui_history_reloaded_signal = Signal(str, list)
    ui_stream_success_signal = Signal(str)
    ui_stream_failed_signal = Signal(str)

    INITIAL_STATE = UIMode.IDLE

    def __init__(self, view: "DashboardView", container: "IContainer") -> None:
        super().__init__(view, container)

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

        # Register Lifecycle Hooks for custom behaviors
        self.fsm.on_enter(UIMode.ERROR, self._on_fsm_error)

        # Force initial UI apply
        self.view.control_card.apply_ui_mode(UIMode.IDLE)

        self.active_charts: dict = {}

        # Must be called explicitly at the end of __init__ per BasePresenter contract.
        self._connect_ui_signals()
        self._connect_engine_events()

    # ================================================================== #
    # BasePresenter contract implementations
    # ================================================================== #

    def _connect_ui_signals(self) -> None:
        """Kết nối các thao tác bấm nút từ thẻ Card vào Presenter."""
        # ControlCard signals
        self.view.control_card.sig_load_clicked.connect(self._on_load_history)
        self.view.control_card.sig_start_clicked.connect(self._on_start_stream)
        self.view.control_card.sig_stop_clicked.connect(self._on_stop_stream)

        # MonitorCard signals
        self.view.monitor_card.clear_logs_clicked.connect(self._on_clear_logs)

        # Internal signals → view update slots (all execute on the Qt main thread)
        self.ui_log_signal.connect(self.view.monitor_card.append_log)
        self.ui_chart_update_signal.connect(self._on_ui_chart_update)

        # Signals for Auto-Sync Workflow
        self.ui_history_reloaded_signal.connect(self._on_history_reloaded)
        self.ui_stream_success_signal.connect(self._on_stream_start_success)
        self.ui_stream_failed_signal.connect(self._on_stream_start_failed)

    def _connect_engine_events(self) -> None:
        """Đăng ký lắng nghe sự kiện từ Engine EventBus."""
        self.event_bus.on(MarketTickEvent, self._handle_market_tick)

    # ================================================================== #
    # FSM Hooks
    # ================================================================== #

    def _on_fsm_error(self) -> None:
        """Auto-recover to IDLE immediately after entering the ERROR state."""
        self.fsm.transition_to(UIMode.IDLE)

    # ================================================================== #
    # UI Helpers
    # ================================================================== #

    def _ensure_chart_cards(self, symbols: List[str]) -> list:
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
        return chart_cards

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
        self.view.monitor_card.append_log(
            "Loading historical data from local database..."
        )
        symbols = list(_DEFAULT_SYMBOLS)
        self._ensure_chart_cards(symbols)
        self._thread_manager.submit(
            self._run_load_history, symbols, _DEFAULT_INTERVAL_STR, _DEFAULT_KLINE_LIMIT
        )

    @Slot()
    @safe_ui_action
    def _on_start_stream(self) -> None:
        """
        Lock the UI and submit the full Auto-Sync → Stream startup workflow
        as a single background task.
        """
        self.view.monitor_card.append_log("Starting Live Stream (Auto-Sync)...")
        self.fsm.transition_to(UIMode.LOCKED)

        symbols = list(_DEFAULT_SYMBOLS)
        interval = TimeFrame(_DEFAULT_INTERVAL_STR)

        # Prepare chart cards on the main thread (safe: view state only).
        chart_cards = self._ensure_chart_cards(symbols)
        self.ui_log_signal.emit(f"Prepared {len(chart_cards)} charts.")

        self._thread_manager.submit(
            self._run_sync_and_start,
            symbols,
            interval,
            _DEFAULT_INTERVAL_STR,
            _DEFAULT_KLINE_LIMIT,
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
        self.view.monitor_card.append_log("Stopping Live Stream...")
        try:
            cmd = StopLiveStreamCommand()
            self.dispatcher.dispatch(StopLiveStreamCommand, cmd)
            self.ui_log_signal.emit("Live Stream stopped.")
            self.fsm.transition_to(UIMode.IDLE)
        except Exception as exc:
            self.ui_log_signal.emit(f"Error while stopping: {exc}")
            self.fsm.transition_to(UIMode.ERROR)

    @Slot()
    @safe_ui_action
    def _on_run_backtest(self) -> None:
        self.ui_log_signal.emit("Starting Backtest simulation...")
        self.view.control_card.set_backtest_active(True)
        # TODO: Dispatch RunBacktestCommand

    @Slot()
    @safe_ui_action
    def _on_stop_backtest(self) -> None:
        self.ui_log_signal.emit("Backtest stopped.")
        self.view.control_card.set_backtest_active(False)

    @Slot()
    @safe_ui_action
    def _on_clear_logs(self) -> None:
        self.view.monitor_card.clear_logs()

    # ================================================================== #
    # Background Signal Slots — called on the main thread via Qt signals.
    # ================================================================== #

    @Slot(str, list)
    def _on_history_reloaded(self, symbol: str, mapped_data: list) -> None:
        """Receives pre-mapped kline data from the background and renders to chart."""
        card = self.active_charts.get(symbol)
        if card:
            card.render_historical_data(mapped_data)
            self.ui_log_signal.emit(
                f"Refreshed {len(mapped_data)} historical klines for {symbol}."
            )

    # ================================================================== #
    # Engine Event Bridge — called from background threads.
    # MUST NOT touch Qt widgets. Use signals only.
    # ================================================================== #

    def _handle_market_tick(self, event: MarketTickEvent) -> None:
        """
        @warning Called by EventBus from a background thread.
        Never touch UI widgets here — emit signals only.
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
            is_closed,
        )

    @Slot(str, float, float, float, float, float, bool)
    def _on_ui_chart_update(
        self,
        symbol: str,
        t: float,
        o: float,
        h: float,
        low: float,
        c: float,
        is_closed: bool,
    ) -> None:
        """
        @brief Được gọi trong Main UI Thread một cách an toàn thông qua Signal.
        Chỉ thực hiện tra cứu O(1) và đẩy data vào đúng ChartCard tương ứng.
        """
        card = self.active_charts.get(symbol)
        if card:
            if is_closed:
                card.append_closed_candle(t, o, h, low, c)
            else:
                card.update_last_candle(t, o, h, low, c)

    # ================================================================== #
    # Background methods — submitted to IThreadManager.
    # MUST NOT touch Qt widgets directly. Use signals only.
    # ================================================================== #

    def _run_load_history(
        self, symbols: List[str], interval_str: str, limit: int
    ) -> None:
        """
        @brief Background worker: queries historical klines for each symbol and
        emits results via ui_history_reloaded_signal for safe main-thread rendering.
        """
        for symbol in symbols:
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
                    self.ui_log_signal.emit(f"No historical data found for {symbol}.")
                    continue

                # Reverse: DB returned newest-first, chart expects oldest-first
                mapped_data = self._map_klines(list(reversed(klines)))
                self.ui_history_reloaded_signal.emit(symbol, mapped_data)

            except Exception as exc:
                self.ui_log_signal.emit(
                    f"Exception while loading history for {symbol}: {exc}"
                )

    def _run_sync_and_start(
        self,
        symbols: List[str],
        interval: TimeFrame,
        interval_str: str,
        limit: int,
    ) -> None:
        """
        @brief Background worker for the full Auto-Sync → Load History → Start Stream
        workflow. All three steps run sequentially in one background thread.
        Results are communicated back to the UI exclusively via signals.
        """
        try:
            # Step 1: Auto-Sync (fill any data gaps)
            self.ui_log_signal.emit("Syncing missing data from Binance...")
            sync_cmd = SyncMarketDataCommand(symbols=symbols, interval=interval)
            self.dispatcher.dispatch(SyncMarketDataCommand, sync_cmd)

            # Step 2: Reload historical data onto charts
            self.ui_log_signal.emit("Reloading historical data onto charts...")
            for symbol in symbols:
                query = GetHistoricalKlinesQuery(
                    symbol=symbol,
                    interval=interval_str,
                    limit=limit,
                    order_by_desc=True,
                )
                response = self.dispatcher.dispatch(GetHistoricalKlinesQuery, query)
                klines = getattr(response, "data", response) if response else []

                if klines and isinstance(klines, list):
                    mapped_data = self._map_klines(list(reversed(klines)))
                    self.ui_history_reloaded_signal.emit(symbol, mapped_data)

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

        except Exception as exc:
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
