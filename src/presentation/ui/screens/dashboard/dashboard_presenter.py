from PySide6.QtCore import QObject, Signal, Slot
from sagittarius_engine import App

# Import Commands 
from Binace_Bot.src.application.use_cases.stream.start_live_stream.command import StartLiveStreamCommand
from Binace_Bot.src.application.use_cases.stream.stop_live_stream.command import StopLiveStreamCommand
from Binace_Bot.src.application.use_cases.queries.get_historical_klines.query import GetHistoricalKlinesQuery
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame
from Binace_Bot.src.domain.events.market_tick_event import MarketTickEvent
from Binace_Bot.src.presentation.ui.utils.ui_safeguard import safe_ui_action

class DashboardPresenter(QObject):
    """
    Não bộ của màn hình Dashboard.
    Nhiệm vụ:
    1. Lắng nghe hành động từ UI (View) -> Gọi hệ thống (Engine).
    2. Lắng nghe sự kiện ngầm từ hệ thống (Engine) -> Cập nhật UI (View) an toàn.
    """
    
    # ==========================================
    # CẦU NỐI TÍN HIỆU (Thread-safe Signal Bridges)
    # Dùng để truyền dữ liệu từ Background Thread về Main UI Thread
    # ==========================================
    ui_log_signal = Signal(str)
    ui_chart_update_signal = Signal(str, float, float, float, float, float, bool)
    
    # Tín hiệu chuyên dụng cho Auto-Sync Workflow
    ui_history_reloaded_signal = Signal(str, list)
    ui_stream_success_signal = Signal(str)
    ui_stream_failed_signal = Signal(str)

    def __init__(self, view: 'DashboardView', app: 'App'):
        super().__init__()
        self.view = view
        self.app = app
        
        # Extract UI Matrix from config file and inject it
        import os, json
        from Binace_Bot.src.presentation.ui.constants import UIMode
        from sagittarius_engine.extensions.fsm.state_machine import BaseStateMachine
        
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
            matrix_path = os.path.join(base_dir, "config", "ui_matrix.json")
            with open(matrix_path, "r") as f:
                ui_matrix = json.load(f)
            self.view.control_card.set_ui_matrix(ui_matrix)
        except Exception as e:
            print(f"Failed to load UI Matrix from config: {e}")

        # Initialize FSM for UI State Management
        self.fsm = BaseStateMachine[UIMode](UIMode.IDLE)
        
        # Define allowed transitions
        self.fsm.add_transition(UIMode.IDLE, UIMode.LOCKED)
        self.fsm.add_transition(UIMode.LOCKED, UIMode.LIVE)
        self.fsm.add_transition(UIMode.LOCKED, UIMode.ERROR)
        self.fsm.add_transition(UIMode.ERROR, UIMode.IDLE)
        self.fsm.add_transition(UIMode.LIVE, UIMode.IDLE)
        self.fsm.add_transition(UIMode.LIVE, UIMode.ERROR) # E.g., for unexpected websocket drops
        
        # Register Lifecycle Hooks (executed on transition)
        self.fsm.on_enter(UIMode.IDLE, self._on_fsm_idle)
        self.fsm.on_enter(UIMode.LOCKED, self._on_fsm_locked)
        self.fsm.on_enter(UIMode.LIVE, self._on_fsm_live)
        self.fsm.on_enter(UIMode.ERROR, self._on_fsm_error)
        
        # Force initial UI apply
        self.view.control_card.apply_ui_mode(UIMode.IDLE)

        self.active_charts = {}

        self._connect_ui_signals()
        self._connect_engine_events()

    def _connect_ui_signals(self):
        """Kết nối các thao tác bấm nút từ thẻ Card vào Presenter"""
        
        # 1. Tín hiệu từ ControlCard
        self.view.control_card.sig_load_clicked.connect(self._on_load_history)
        self.view.control_card.sig_start_clicked.connect(self._on_start_stream)
        self.view.control_card.sig_stop_clicked.connect(self._on_stop_stream)

        # 2. Tín hiệu từ MonitorCard
        self.view.monitor_card.clear_logs_clicked.connect(self._on_clear_logs)

        # 3. Nối cầu tín hiệu cập nhật an toàn vào giao diện
        self.ui_log_signal.connect(self.view.monitor_card.append_log)
        self.ui_chart_update_signal.connect(self._on_ui_chart_update)
        
        # Signals for Auto-Sync Workflow
        self.ui_history_reloaded_signal.connect(self._on_history_reloaded)
        self.ui_stream_success_signal.connect(self._on_stream_start_success)
        self.ui_stream_failed_signal.connect(self._on_stream_start_failed)

    def _connect_engine_events(self):
        """
        Đăng ký lắng nghe các sự kiện ngầm (EventBus) từ sagittarius_engine.
        """
        self.app.event_bus.on(MarketTickEvent, self._handle_market_tick)
        
    # ==========================================
    # FSM HOOKS (Only modify UI state here)
    # ==========================================
    def _on_fsm_idle(self):
        from Binace_Bot.src.presentation.ui.constants import UIMode
        self.view.control_card.apply_ui_mode(UIMode.IDLE)
        
    def _on_fsm_locked(self):
        from Binace_Bot.src.presentation.ui.constants import UIMode
        self.view.control_card.apply_ui_mode(UIMode.LOCKED)
        
    def _on_fsm_live(self):
        from Binace_Bot.src.presentation.ui.constants import UIMode
        self.view.control_card.apply_ui_mode(UIMode.LIVE)
        
    def _on_fsm_error(self):
        from Binace_Bot.src.presentation.ui.constants import UIMode
        self.view.control_card.apply_ui_mode(UIMode.ERROR)
        # Auto-recover to IDLE immediately after applying ERROR state (or wait 1 frame)
        # We can emit a signal or call it directly since we are on MainThread.
        self.fsm.transition_to(UIMode.IDLE)
        
    def _ensure_chart_cards(self, symbols: list[str]) -> list:
        """
        @brief Reuse existing chart cards to prevent history wipeout. 
        Only recreates layout if symbols change or no charts exist.
        """
        current_symbols = list(self.active_charts.keys())
        if set(current_symbols) == set(symbols):
            # Same symbols, reuse existing cards
            return list(self.active_charts.values())
            
        # Different symbols, re-render
        chart_cards = self.view.render_symbol_cards(symbols)
        self.active_charts.clear()
        for card in chart_cards:
            self.active_charts[card.symbol] = card
        return chart_cards

    # ==========================================
    # XỬ LÝ LỆNH TỪ USER (UI -> Engine)
    # ==========================================
    @Slot()
    @safe_ui_action
    def _on_load_history(self):
        self.view.monitor_card.append_log("Loading historical data from local database...")
        
        symbols = ["BTCUSDT", "ETHUSDT"]
        interval = "1m"
        limit = 5000 # Lấy 5000 nến mới nhất
        
        chart_cards = self._ensure_chart_cards(symbols)
        
        for card in chart_cards:
            # Khởi tạo Query lấy data
            query = GetHistoricalKlinesQuery(
                symbol=card.symbol,
                interval=interval,
                limit=limit,
                order_by_desc=True # Phải set True để DB lấy 5000 nến MỚI NHẤT
            )
            
            try:
                response = self.app.dispatch(GetHistoricalKlinesQuery, query)
                klines = getattr(response, 'data', response) if response else []
                
                if not isinstance(klines, list):
                    self.ui_log_signal.emit(f"Data format error for {card.symbol}.")
                    continue
                    
                if not klines:
                    self.ui_log_signal.emit(f"No historical data found for {card.symbol}.")
                    continue
                    
                # Đảo ngược mảng (Reverse) để có thứ tự Cũ -> Mới vẽ biểu đồ
                klines = list(reversed(klines))
                
                # Mapping chuẩn format của FastCandlestickItem (t, o, h, l, c)
                mapped_data = [
                    (
                        float(item.close_time.timestamp()), # Dùng close_time giống tick event
                        float(item.open_price),
                        float(item.high_price),
                        float(item.low_price),
                        float(item.close_price)
                    ) for item in klines
                ]
                
                card.render_historical_data(mapped_data)
                self.ui_log_signal.emit(f"Rendered {len(mapped_data)} historical klines for {card.symbol}.")
                
            except Exception as e:
                self.ui_log_signal.emit(f"Exception while loading history for {card.symbol}: {str(e)}")

    @Slot()
    @safe_ui_action
    def _on_start_stream(self):
        self.view.monitor_card.append_log("Starting Live Stream (Auto-Sync)...")
        
        # 1. UI Locking - Prevent spamming via FSM
        from Binace_Bot.src.presentation.ui.constants import UIMode
        self.fsm.transition_to(UIMode.LOCKED)
        
        symbols = ["BTCUSDT", "ETHUSDT"]
        interval_str = "1m"
        interval = TimeFrame(interval_str)
        limit = 5000
        
        # Tái sử dụng chart
        chart_cards = self._ensure_chart_cards(symbols)
            
        self.ui_log_signal.emit(f"Prepared {len(chart_cards)} charts.")

        # 2. Managed Background Task
        def sync_and_start_task():
            try:
                from Binace_Bot.src.application.use_cases.sync.sync_market_data.command import SyncMarketDataCommand
                
                # Bước 1: Auto-Sync (Fill Gap)
                self.ui_log_signal.emit("Syncing missing data from Binance...")
                sync_cmd = SyncMarketDataCommand(symbols=symbols, interval=interval)
                self.app.dispatch(SyncMarketDataCommand, sync_cmd)
                
                # Bước 2: Truy vấn lại Database để cập nhật Chart
                self.ui_log_signal.emit("Reloading historical data onto charts...")
                for symbol in symbols:
                    query = GetHistoricalKlinesQuery(
                        symbol=symbol,
                        interval=interval_str,
                        limit=limit,
                        order_by_desc=True
                    )
                    response = self.app.dispatch(GetHistoricalKlinesQuery, query)
                    klines = getattr(response, 'data', response) if response else []
                    
                    if klines and isinstance(klines, list):
                        klines = list(reversed(klines))
                        mapped_data = [
                            (
                                float(item.close_time.timestamp()),
                                float(item.open_price),
                                float(item.high_price),
                                float(item.low_price),
                                float(item.close_price)
                            ) for item in klines
                        ]
                        # Bước 3: Đẩy data an toàn về Main Thread
                        self.ui_history_reloaded_signal.emit(symbol, mapped_data)
                
                # Bước 4: Khởi động Live Stream
                self.ui_log_signal.emit("Opening Websocket stream...")
                cmd = StartLiveStreamCommand(symbols=symbols, interval=interval)
                response = self.app.dispatch(StartLiveStreamCommand, cmd)
                
                if response and getattr(response, 'success', True):
                    self.ui_stream_success_signal.emit(f"Live stream for {symbols} is running.")
                else:
                    msg = getattr(response, 'message', 'Unknown error')
                    self.ui_stream_failed_signal.emit(f"Failed to start: {msg}")
                    
            except Exception as e:
                self.ui_stream_failed_signal.emit(f"System error: {str(e)}")
                
        # Thực thi qua Engine Task Manager
        from sagittarius_engine.interfaces.i_thread_manager import IThreadManager
        thread_mgr: IThreadManager = self.app.container.resolve(IThreadManager)
        thread_mgr.submit(sync_and_start_task)

    # ==========================================
    # SLOTS XỬ LÝ BACKGROUND SIGNALS (Chạy trên UI Thread)
    # ==========================================
    @Slot(str, list)
    def _on_history_reloaded(self, symbol: str, mapped_data: list):
        card = self.active_charts.get(symbol)
        if card:
            card.render_historical_data(mapped_data)
            self.ui_log_signal.emit(f"Refreshed {len(mapped_data)} historical klines for {symbol}.")
            
    @Slot(str)
    def _on_stream_start_success(self, msg: str):
        self.ui_log_signal.emit(msg)
        from Binace_Bot.src.presentation.ui.constants import UIMode
        self.fsm.transition_to(UIMode.LIVE)
        
    @Slot(str)
    def _on_stream_start_failed(self, msg: str):
        self.ui_log_signal.emit(f"Stream startup failed: {msg}")
        # Transition via ERROR to IDLE
        from Binace_Bot.src.presentation.ui.constants import UIMode
        self.fsm.transition_to(UIMode.ERROR)

    @Slot()
    @safe_ui_action
    def _on_stop_stream(self):
        self.view.monitor_card.append_log("Stopping Live Stream...")
        
        try:
            cmd = StopLiveStreamCommand()
            response = self.app.dispatch(StopLiveStreamCommand, cmd)
            self.ui_log_signal.emit("Live Stream stopped.")
            from Binace_Bot.src.presentation.ui.constants import UIMode
            self.fsm.transition_to(UIMode.IDLE)
        except Exception as e:
            self.ui_log_signal.emit(f"Error while stopping: {str(e)}")
            from Binace_Bot.src.presentation.ui.constants import UIMode
            self.fsm.transition_to(UIMode.ERROR)

    @Slot()
    @safe_ui_action
    def _on_run_backtest(self):
        self.ui_log_signal.emit("Starting Backtest simulation...")
        self.view.control_card.set_backtest_active(True)
        # TODO: Dispatch RunBacktestCommand

    @Slot()
    @safe_ui_action
    def _on_stop_backtest(self):
        self.ui_log_signal.emit("Backtest stopped.")
        self.view.control_card.set_backtest_active(False)

    @Slot()
    @safe_ui_action
    def _on_clear_logs(self):
        self.view.monitor_card.clear_logs()

    # ==========================================
    # XỬ LÝ SỰ KIỆN HỆ THỐNG (Engine -> UI)
    # ==========================================
    def _handle_market_tick(self, event: MarketTickEvent):
        """
        [CẢNH BÁO TỬ THẦN]: Hàm này bị EventBus gọi từ Background Thread.
        Tuyệt đối không gọi UI Update trực tiếp tại đây. Phải ném qua Signal.
        """
        # Trích xuất dữ liệu từ MarketData
        symbol = event.market_data.symbol
        t = event.market_data.close_time.timestamp()
        o = event.market_data.open_price
        h = event.market_data.high_price
        l = event.market_data.low_price
        c = event.market_data.close_price
        is_closed = event.market_data.is_closed
        
        self.ui_chart_update_signal.emit(symbol, t, o, h, l, c, is_closed)

    @Slot(str, float, float, float, float, float, bool)
    def _on_ui_chart_update(self, symbol: str, t: float, o: float, h: float, l: float, c: float, is_closed: bool):
        """
        Được gọi trong Main UI Thread một cách an toàn thông qua Signal.
        Chỉ thực hiện tra cứu O(1) và đẩy data vào đúng ChartCard tương ứng.
        """
        card = self.active_charts.get(symbol)
        if card:
            if is_closed:
                card.append_closed_candle(t, o, h, l, c)
            else:
                card.update_last_candle(t, o, h, l, c)
