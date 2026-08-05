from PySide6.QtCore import QObject, Signal, Slot
from sagittarius_engine import App

# Import Commands 
from Binace_Bot.src.application.use_cases.stream.start_live_stream.command import StartLiveStreamCommand
from Binace_Bot.src.application.use_cases.stream.stop_live_stream.command import StopLiveStreamCommand
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame

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
    # ui_chart_update_signal = Signal(dict) # Bỏ comment khi tích hợp ChartCard

    def __init__(self, view, app: App):
        super().__init__()
        self.view = view
        self.app = app

        self._connect_ui_signals()
        self._connect_engine_events()

    def _connect_ui_signals(self):
        """Kết nối các thao tác bấm nút từ thẻ Card vào Presenter"""
        
        # 1. Tín hiệu từ ControlCard
        self.view.control_card.start_stream_clicked.connect(self._on_start_stream)
        self.view.control_card.stop_stream_clicked.connect(self._on_stop_stream)
        self.view.control_card.run_backtest_clicked.connect(self._on_run_backtest)
        self.view.control_card.stop_backtest_clicked.connect(self._on_stop_backtest)

        # 2. Tín hiệu từ MonitorCard
        self.view.monitor_card.clear_logs_clicked.connect(self._on_clear_logs)

        # 3. Nối cầu tín hiệu cập nhật an toàn vào giao diện
        self.ui_log_signal.connect(self.view.monitor_card.append_log)

    def _connect_engine_events(self):
        """
        Đăng ký lắng nghe các sự kiện ngầm (EventBus) từ sagittarius_engine.
        """
        # Ví dụ: Bắt sự kiện khi WebSocket nhận tick giá mới hoặc khi lưu Database
        # self.app.event_bus.on(SystemLogEvent, self._handle_background_log)
        pass

    # ==========================================
    # XỬ LÝ LỆNH TỪ USER (UI -> Engine)
    # ==========================================
    @Slot()
    def _on_start_stream(self):
        self.view.monitor_card.append_log("⏳ Đang khởi động Live Stream...")
        
        # Lấy danh sách symbol (hiện tại hardcode, sau này lấy từ Model/Config)
        symbols = ["BTCUSDT", "ETHUSDT"]
        interval = TimeFrame("1m")
        
        # 1. Báo View tự động render danh sách ChartCard
        chart_cards = self.view.render_symbol_cards(symbols)
        
        # 2. Vòng lặp: Connect tự động toàn bộ tín hiệu của các Card động mới sinh ra
        for card in chart_cards:
            # Ví dụ: Nếu ChartCard có nút "Stop riêng", ta sẽ connect ở đây
            # card.stop_clicked.connect(self._on_stop_single_stream)
            pass
            
        self.ui_log_signal.emit(f"Đã render {len(chart_cards)} biểu đồ động.")

        try:
            cmd = StartLiveStreamCommand(symbols=symbols, interval=interval)
            response = self.app.dispatch(StartLiveStreamCommand, cmd)
            
            if response and getattr(response, 'success', True):
                self.ui_log_signal.emit(f"✅ Live stream {symbols} đã chạy ngầm.")
                self.view.control_card.set_stream_active(True)
            else:
                msg = getattr(response, 'message', 'Lỗi không xác định')
                self.ui_log_signal.emit(f"❌ Khởi động thất bại: {msg}")
                
        except Exception as e:
            self.ui_log_signal.emit(f"❌ Lỗi hệ thống: {str(e)}")

    @Slot()
    def _on_stop_stream(self):
        self.view.monitor_card.append_log("⏳ Đang dừng Live Stream...")
        
        try:
            cmd = StopLiveStreamCommand()
            response = self.app.dispatch(StopLiveStreamCommand, cmd)
            self.ui_log_signal.emit("🛑 Đã dừng Live Stream.")
            self.view.control_card.set_stream_active(False)
        except Exception as e:
            self.ui_log_signal.emit(f"❌ Lỗi khi dừng: {str(e)}")

    @Slot()
    def _on_run_backtest(self):
        self.ui_log_signal.emit("⚙️ Bắt đầu giả lập Backtest...")
        self.view.control_card.set_backtest_active(True)
        # TODO: Dispatch RunBacktestCommand

    @Slot()
    def _on_stop_backtest(self):
        self.ui_log_signal.emit("🛑 Đã dừng Backtest.")
        self.view.control_card.set_backtest_active(False)

    @Slot()
    def _on_clear_logs(self):
        self.view.monitor_card.clear_logs()

    # ==========================================
    # XỬ LÝ SỰ KIỆN HỆ THỐNG (Engine -> UI)
    # ==========================================
    def _handle_background_log(self, event):
        """
        [CẢNH BÁO TỬ THẦN]: Hàm này bị EventBus gọi từ Background Thread.
        Tuyệt đối không gọi `self.view.monitor_card.append_log()` trực tiếp tại đây.
        """
        # Lấy dữ liệu từ event và ném qua luồng chính thông qua Signal
        log_message = f"Hệ thống: {event.message}"
        self.ui_log_signal.emit(log_message)
