# PROJECT CONTEXT

**Roots:**
- `C:\Users\hoang\Documents\Sagittarius_ForkBoy\Binace_Bot\src\presentation\ui\`

**Pattern:** `*.py`
**Generated:** 2026-08-05 21:24:02

## Directory Tree: C:\Users\hoang\Documents\Sagittarius_ForkBoy\Binace_Bot\src\presentation\ui\

```
ui
├── components
│   ├── __init__.py
│   ├── base_card.py
│   ├── chart_card.py
│   ├── control_card.py
│   └── monitor_card.py
├── main_window.py
├── router.py
└── screens
    └── dashboard
        ├── dashboard_presenter.py
        └── dashboard_view.py
```

---

# FILE: components\__init__.py

```python

``````

# FILE: components\base_card.py

```python
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QWidget
from PySide6.QtCore import Qt

class BaseCard(QFrame):
    
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("base_card")

self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        self._setup_header(title)
        self._setup_body()
        self._setup_footer()

    def _setup_header(self, title: str):
        self.header = QFrame()
        self.header.setObjectName("base_card_header")
        
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(15, 10, 15, 10)

self.lbl_title = QLabel(title)
        self.lbl_title.setObjectName("base_card_title")
        
        header_layout.addWidget(self.lbl_title)
        header_layout.addStretch()
        
        self.main_layout.addWidget(self.header)

    def _setup_body(self):
        self.body = QWidget()
        self.body.setObjectName("base_card_body")

self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(15, 15, 15, 15)
        self.body_layout.setSpacing(10)
        
        self.main_layout.addWidget(self.body, 1)

    def _setup_footer(self):
        self.footer = QWidget()
        self.footer.setObjectName("base_card_footer")
        self.footer.setVisible(False)
        
        self.footer_layout = QHBoxLayout(self.footer)
        self.footer_layout.setContentsMargins(15, 10, 15, 10)
        
        self.main_layout.addWidget(self.footer)

    def add_to_header(self, widget: QWidget):
        
        self.header.layout().addWidget(widget)

    def add_to_footer(self, widget: QWidget):
        
        self.footer.setVisible(True)
        self.footer.layout().addWidget(widget)
``````

# FILE: components\chart_card.py

```python
import pyqtgraph as pg
from PySide6 import QtCore, QtGui
from PySide6.QtWidgets import QVBoxLayout
from Binace_Bot.src.presentation.ui.components.base_card import BaseCard

class FastCandlestickItem(pg.GraphicsObject):
    
    def __init__(self, data=None):
        pg.GraphicsObject.__init__(self)
        self.picture = QtGui.QPicture()

self.bull_color = QtGui.QColor("
        self.bear_color = QtGui.QColor("
        
        self.candle_width = 20.0
        self.live_candle = None
        
        if data:
            self.generate_picture(data)
            
    def generate_picture(self, data: list[tuple[float, float, float, float, float]]):
        
        self.picture = QtGui.QPicture()
        p = QtGui.QPainter(self.picture)
        
        bull_brush = pg.mkBrush(self.bull_color)
        bull_pen = pg.mkPen(self.bull_color)
        bear_brush = pg.mkBrush(self.bear_color)
        bear_pen = pg.mkPen(self.bear_color)

if len(data) > 1:
            self.candle_width = (data[1][0] - data[0][0]) / 3.0
            
        for (t, o, h, l, c) in data:
            if c >= o:
                p.setPen(bull_pen)
                p.setBrush(bull_brush)
            else:
                p.setPen(bear_pen)
                p.setBrush(bear_brush)

p.drawLine(QtCore.QPointF(t, l), QtCore.QPointF(t, h))

rect = QtCore.QRectF(t - self.candle_width, o, self.candle_width * 2, c - o)
            p.drawRect(rect)
            
        p.end()
        self.prepareGeometryChange()
        self.informViewBoundsChanged()
        
    def paint(self, p: QtGui.QPainter, *args):

p.drawPicture(0, 0, self.picture)

if self.live_candle:
            t, o, h, l, c = self.live_candle
            if c >= o:
                p.setPen(pg.mkPen(self.bull_color))
                p.setBrush(pg.mkBrush(self.bull_color))
            else:
                p.setPen(pg.mkPen(self.bear_color))
                p.setBrush(pg.mkBrush(self.bear_color))
                
            p.drawLine(QtCore.QPointF(t, l), QtCore.QPointF(t, h))
            rect = QtCore.QRectF(t - self.candle_width, o, self.candle_width * 2, c - o)
            p.drawRect(rect)
            
    def update_live_candle(self, t: float, o: float, h: float, l: float, c: float):
        
        self.live_candle = (t, o, h, l, c)
        self.update()
        
    def boundingRect(self) -> QtCore.QRectF:
        
        rect = QtCore.QRectF(self.picture.boundingRect())
        
        if self.live_candle:
            t, o, h, l, c = self.live_candle
            w = self.candle_width

            live_rect = QtCore.QRectF(t - w, l, w * 2, h - l)
            rect = rect.united(live_rect)
            
        return rect

class ChartCard(BaseCard):
    
    def __init__(self, symbol: str, parent=None):
        super().__init__(title=f"Live Chart: {symbol}", parent=parent)
        self.symbol = symbol
        self._setup_content()

    def _setup_content(self):
        pg.setConfigOptions(antialias=True)

date_axis = pg.DateAxisItem(orientation='bottom')
        
        self.plot_widget = pg.PlotWidget(axisItems={'bottom': date_axis})

        self.plot_widget.setBackground('
        self.plot_widget.showGrid(x=True, y=True, alpha=0.2)

self.candlestick = FastCandlestickItem()
        self.plot_widget.addItem(self.candlestick)
        
        self.body_layout.addWidget(self.plot_widget)

    def set_symbol_title(self, symbol: str) -> None:
        self.symbol = symbol
        self.lbl_title.setText(f"Live Chart: {symbol}")
        
    def render_historical_data(self, data: list[tuple[float, float, float, float, float]]) -> None:
        
        self.candlestick.generate_picture(data)
        self.plot_widget.autoRange()
        
    def update_last_candle(self, timestamp: float, open_p: float, high_p: float, low_p: float, close_p: float) -> None:
        
        self.candlestick.update_live_candle(timestamp, open_p, high_p, low_p, close_p)
        
    def cleanup(self) -> None:
        
        self.plot_widget.clear()

if __name__ == "__main__":
    import sys
    import time
    import random
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QTimer

    app = QApplication(sys.argv)

app.setStyleSheet()
    
    card = ChartCard("BTCUSDT")
    card.resize(900, 500)
    card.show()
    
    print("⏳ Tự động sinh 10,000 nến lịch sử (Historical Data)...")
    now = time.time()
    history = []
    base_price = 60000.0

for i in range(10000):
        t = now - (10000 - i) * 60
        o = base_price
        c = o + random.uniform(-100, 100)
        h = max(o, c) + random.uniform(0, 50)
        l = min(o, c) - random.uniform(0, 50)
        history.append((t, o, h, l, c))
        base_price = c
        
    card.render_historical_data(history)
    print("✅ Đã load xong 10,000 nến vào Cache.")

live_t = now + 60
    live_o = base_price
    live_h = live_o
    live_l = live_o
    live_c = live_o
    
    def on_live_tick():
        global live_h, live_l, live_c

live_c += random.uniform(-10, 10)
        live_h = max(live_h, live_c)
        live_l = min(live_l, live_c)

card.update_last_candle(live_t, live_o, live_h, live_l, live_c)
        
    timer = QTimer()
    timer.timeout.connect(on_live_tick)
    timer.start(100)
    print("⚡ Bắn Live Tick 100ms/lần. Bạn hãy thử zoom in/out để cảm nhận độ mượt!")
    
    sys.exit(app.exec())
``````

# FILE: components\control_card.py

```python
from PySide6.QtWidgets import QPushButton
from PySide6.QtCore import Signal
from Binace_Bot.src.presentation.ui.components.base_card import BaseCard

class ControlCard(BaseCard):

start_stream_clicked = Signal()
    stop_stream_clicked = Signal()
    run_backtest_clicked = Signal()
    stop_backtest_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(title="System Controls", parent=parent)
        self._setup_content()
        self.set_stream_active(False)
        self.set_backtest_active(False)

    def _setup_content(self):

        self.btn_start_stream = QPushButton("Start Live Stream")
        self.btn_stop_stream = QPushButton("Stop Live Stream")
        self.btn_run_backtest = QPushButton("Run Backtest")
        self.btn_stop_backtest = QPushButton("Stop Backtest")

self.btn_start_stream.clicked.connect(self.start_stream_clicked.emit)
        self.btn_stop_stream.clicked.connect(self.stop_stream_clicked.emit)
        self.btn_run_backtest.clicked.connect(self.run_backtest_clicked.emit)
        self.btn_stop_backtest.clicked.connect(self.stop_backtest_clicked.emit)

self.body_layout.addWidget(self.btn_start_stream)
        self.body_layout.addWidget(self.btn_stop_stream)
        self.body_layout.addWidget(self.btn_run_backtest)
        self.body_layout.addWidget(self.btn_stop_backtest)
        self.body_layout.addStretch()

    def set_stream_active(self, is_active: bool) -> None:
        self.btn_start_stream.setEnabled(not is_active)
        self.btn_stop_stream.setEnabled(is_active)
        
    def set_backtest_active(self, is_active: bool) -> None:
        self.btn_run_backtest.setEnabled(not is_active)
        self.btn_stop_backtest.setEnabled(is_active)
``````

# FILE: components\monitor_card.py

```python
from PySide6.QtWidgets import QTextEdit, QPushButton
from PySide6.QtCore import Signal
from datetime import datetime
from Binace_Bot.src.presentation.ui.components.base_card import BaseCard

class MonitorCard(BaseCard):

clear_logs_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(title="System Monitor", parent=parent)
        self._setup_content()

    def _setup_content(self):

        self.btn_clear = QPushButton("Clear")
        self.btn_clear.setMaximumWidth(80)
        self.btn_clear.clicked.connect(self.clear_logs_clicked.emit)
        self.add_to_header(self.btn_clear)

self.text_edit = QTextEdit()
        self.text_edit.setObjectName("terminal_log")
        self.text_edit.setReadOnly(True)
        
        self.body_layout.addWidget(self.text_edit)

    def append_log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.text_edit.append(f"[{timestamp}] {message}")
        
    def clear_logs(self) -> None:
        self.text_edit.clear()
``````

# FILE: main_window.py

```python
import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, 
    QVBoxLayout, QPushButton, QStackedWidget, QLabel
)
from PySide6.QtCore import Qt

class MainWindow(QMainWindow):
    
    def __init__(self, app_engine):
        super().__init__()
        self.app = app_engine
        self.setWindowTitle("Binance Bot Desktop - Clean Architecture")
        self.resize(1200, 800)

central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

sidebar_widget = QWidget()
        sidebar_widget.setMaximumWidth(250)
        sidebar_widget.setStyleSheet("background-color:
        self.sidebar = QVBoxLayout(sidebar_widget)
        self.sidebar.setAlignment(Qt.AlignTop)
        self.sidebar.setContentsMargins(10, 20, 10, 20)
        self.sidebar.setSpacing(10)

self.stacked_widget = QStackedWidget()
        self.stacked_widget.setStyleSheet("background-color:

main_layout.addWidget(sidebar_widget)
        main_layout.addWidget(self.stacked_widget)
        
        self._setup_sidebar()
        self._setup_screens()

    def _setup_sidebar(self):

        app_title = QLabel("Binance Bot")
        app_title.setStyleSheet("font-size: 20px; font-weight: bold; margin-bottom: 20px;")
        app_title.setAlignment(Qt.AlignCenter)
        self.sidebar.addWidget(app_title)

self.btn_dashboard = QPushButton("Dashboard")
        self.btn_dashboard.setCheckable(True)
        self.btn_dashboard.setChecked(True)
        self.btn_dashboard.setMinimumHeight(40)
        self.btn_dashboard.clicked.connect(lambda: self.switch_screen("dashboard"))

self.btn_backtest = QPushButton("Backtest")
        self.btn_backtest.setCheckable(True)
        self.btn_backtest.setMinimumHeight(40)
        self.btn_backtest.clicked.connect(lambda: self.switch_screen("backtest"))
        
        self.sidebar.addWidget(self.btn_dashboard)
        self.sidebar.addWidget(self.btn_backtest)

    def _setup_screens(self):
        from Binace_Bot.src.presentation.ui.router import RouterManager
        
        self.router = RouterManager(self.stacked_widget, self.app)

self.router.register_route("dashboard", self._factory_dashboard)
        self.router.register_route("backtest", self._factory_backtest)

self.router.navigate("dashboard")

    def _factory_dashboard(self, app):
        from Binace_Bot.src.presentation.ui.screens.dashboard.dashboard_view import DashboardView
        from Binace_Bot.src.presentation.ui.screens.dashboard.dashboard_presenter import DashboardPresenter
        
        view = DashboardView()

        view.presenter = DashboardPresenter(view, app)
        return view

    def _factory_backtest(self, app):
        from PySide6.QtWidgets import QLabel

        backtest_widget = QLabel("Backtest Screen (Under Construction)")
        backtest_widget.setAlignment(Qt.AlignCenter)
        backtest_widget.setStyleSheet("font-size: 24px; color:
        return backtest_widget

    def switch_screen(self, route_name: str):
        self.router.navigate(route_name)

        self.btn_dashboard.setChecked(route_name == "dashboard")
        self.btn_backtest.setChecked(route_name == "backtest")

def main():
    import sys
    from PySide6.QtWidgets import QApplication
    from Binace_Bot.src.main import create_app
    from sagittarius_engine.infrastructure.config.config_manager import ConfigManager
    from sagittarius_engine.utils.path_utils import PathUtils
    import os

config_manager = ConfigManager()
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    app_json = os.path.join(base_dir, "config", "app_config.json")
    user_json = os.path.join(base_dir, "config", "user_config.json")
    
    config_manager.load_json(app_json)
    config_manager.load_json(user_json)
    
    app_engine = create_app(config_manager)
    app_engine.boot()

app = QApplication(sys.argv)
    app.setStyle("Fusion")

qss_path = os.path.join(base_dir, "src", "presentation", "ui", "qss", "style.qss")
    if os.path.exists(qss_path):
        with open(qss_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
            
    window = MainWindow(app_engine)
    window.show()
    
    exit_code = app.exec()

app_engine.stop()
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
``````

# FILE: router.py

```python
from PySide6.QtWidgets import QStackedWidget
from sagittarius_engine import App

class RouterManager:
    
    def __init__(self, stacked_widget: QStackedWidget, app: App):
        self.stacked_widget = stacked_widget
        self.app = app

self.routes = {}
        
    def register_route(self, route_name: str, factory: callable):
        
        self.routes[route_name] = {
            'factory': factory,
            'instance': None,
            'index': -1
        }

    def navigate(self, route_name: str):
        
        if route_name not in self.routes:
            raise ValueError(f"Route '{route_name}' not registered.")
            
        route_info = self.routes[route_name]

if route_info['instance'] is None:

            view = route_info['factory'](self.app)
            route_info['instance'] = view

index = self.stacked_widget.addWidget(view)
            route_info['index'] = index

self.stacked_widget.setCurrentIndex(route_info['index'])
``````

# FILE: screens\dashboard\dashboard_presenter.py

```python
from PySide6.QtCore import QObject, Signal, Slot
from sagittarius_engine import App

from Binace_Bot.src.application.use_cases.stream.start_live_stream.command import StartLiveStreamCommand
from Binace_Bot.src.application.use_cases.stream.stop_live_stream.command import StopLiveStreamCommand
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame
from Binace_Bot.src.domain.events.market_tick_event import MarketTickEvent

class DashboardPresenter(QObject):

ui_log_signal = Signal(str)
    ui_chart_update_signal = Signal(str, float, float, float, float, float)

    def __init__(self, view, app: App):
        super().__init__()
        self.view = view
        self.app = app
        self.active_charts = {}

        self._connect_ui_signals()
        self._connect_engine_events()

    def _connect_ui_signals(self):

self.view.control_card.start_stream_clicked.connect(self._on_start_stream)
        self.view.control_card.stop_stream_clicked.connect(self._on_stop_stream)
        self.view.control_card.run_backtest_clicked.connect(self._on_run_backtest)
        self.view.control_card.stop_backtest_clicked.connect(self._on_stop_backtest)

self.view.monitor_card.clear_logs_clicked.connect(self._on_clear_logs)

self.ui_log_signal.connect(self.view.monitor_card.append_log)
        self.ui_chart_update_signal.connect(self._on_ui_chart_update)

    def _connect_engine_events(self):
        
        self.app.event_bus.on(MarketTickEvent, self._handle_market_tick)

@Slot()
    def _on_start_stream(self):
        self.view.monitor_card.append_log("⏳ Đang khởi động Live Stream...")

symbols = ["BTCUSDT", "ETHUSDT"]
        interval = TimeFrame("1m")

chart_cards = self.view.render_symbol_cards(symbols)
        self.active_charts.clear()

for card in chart_cards:
            self.active_charts[card.symbol] = card
            
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

@Slot()
    def _on_stop_backtest(self):
        self.ui_log_signal.emit("🛑 Đã dừng Backtest.")
        self.view.control_card.set_backtest_active(False)

    @Slot()
    def _on_clear_logs(self):
        self.view.monitor_card.clear_logs()

def _handle_market_tick(self, event: MarketTickEvent):

symbol = event.market_data.symbol
        t = event.market_data.close_time.timestamp()
        o = event.market_data.open_price
        h = event.market_data.high_price
        l = event.market_data.low_price
        c = event.market_data.close_price
        
        self.ui_chart_update_signal.emit(symbol, t, o, h, l, c)

    @Slot(str, float, float, float, float, float)
    def _on_ui_chart_update(self, symbol: str, t: float, o: float, h: float, l: float, c: float):
        
        card = self.active_charts.get(symbol)
        if card:
            card.update_last_candle(t, o, h, l, c)
``````

# FILE: screens\dashboard\dashboard_view.py

```python
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QFrame, QLabel, QScrollArea
from PySide6.QtCore import Qt
from Binace_Bot.src.presentation.ui.components.control_card import ControlCard
from Binace_Bot.src.presentation.ui.components.monitor_card import MonitorCard

class DashboardView(QWidget):
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)

self.charts_container = QWidget()
        self.charts_layout = QVBoxLayout(self.charts_container)
        self.charts_layout.setContentsMargins(0, 0, 0, 0)
        self.charts_layout.setSpacing(15)
        self.charts_layout.addStretch()
        
        self.scroll_area.setWidget(self.charts_container)

right_column = QVBoxLayout()
        right_column.setSpacing(20)

self.control_card = ControlCard()
        self.monitor_card = MonitorCard()

        right_column.addWidget(self.control_card, 1)
        right_column.addWidget(self.monitor_card, 3)

main_layout.addWidget(self.scroll_area, 3)
        main_layout.addLayout(right_column, 1)

    def render_symbol_cards(self, symbols: list[str]) -> list:

for i in reversed(range(self.charts_layout.count() - 1)): 
            item = self.charts_layout.itemAt(i)
            widget = item.widget()
            if widget:

                if hasattr(widget, 'cleanup'):
                    widget.cleanup()

self.charts_layout.removeItem(item)

widget.deleteLater()
                
        self.chart_cards = []

stretch_index = self.charts_layout.count() - 1
        
        for symbol in symbols:
            from Binace_Bot.src.presentation.ui.components.chart_card import ChartCard
            card = ChartCard(symbol)
            self.chart_cards.append(card)
            self.charts_layout.insertWidget(stretch_index, card)
            stretch_index += 1
            
        return self.chart_cards
``````

