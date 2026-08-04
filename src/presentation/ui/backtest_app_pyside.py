import os
import sys
import time
import pandas as pd
from datetime import datetime
import threading
import pyqtgraph as pg

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

from Binace_Bot.src.main import create_app
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame
from Binace_Bot.src.domain.events.market_tick_event import MarketTickEvent
from Binace_Bot.src.application.use_cases.run_backtest import RunBacktestCommand
from sagittarius_engine.utils.path_utils import PathUtils

from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from PySide6.QtCore import QObject, Signal, Slot, QRectF
from PySide6.QtGui import QPicture, QPainter, QColor

class CandlestickItem(pg.GraphicsObject):
    def __init__(self):
        pg.GraphicsObject.__init__(self)
        self.data = [] # List of tuples: (time_index, open, high, low, close)
        self.picture = QPicture()

    def set_data(self, data):
        self.data = data
        self.generatePicture()
        self.informViewBoundsChanged()
        
    def add_data(self, item):
        self.data.append(item)
        self.generatePicture()
        self.informViewBoundsChanged()

    def generatePicture(self):
        self.picture = QPicture()
        p = QPainter(self.picture)
        
        # Optimize rendering by grouping green and red candles
        w = 0.3 # half-width of candle
        for t, open_p, high_p, low_p, close_p in self.data:
            # Set color based on price action
            if close_p > open_p:
                p.setPen(pg.mkPen('g'))
                p.setBrush(pg.mkBrush('g'))
            else:
                p.setPen(pg.mkPen('r'))
                p.setBrush(pg.mkBrush('r'))
            
            # Draw wick (high to low)
            p.drawLine(pg.QtCore.QPointF(t, low_p), pg.QtCore.QPointF(t, high_p))
            
            # Draw body (open to close)
            # Y-axis goes up, so rect is (x, min_y, width, height)
            min_y = min(open_p, close_p)
            height = abs(open_p - close_p)
            
            # A body can have zero height, so force at least a small line
            if height == 0:
                p.drawLine(pg.QtCore.QPointF(t - w, open_p), pg.QtCore.QPointF(t + w, open_p))
            else:
                p.drawRect(QRectF(t - w, min_y, w * 2, height))
        
        p.end()
        self.update() # Request repaint

    def paint(self, p, *args):
        p.drawPicture(0, 0, self.picture)

    def boundingRect(self):
        # Calculate bounding rect to allow auto-scaling
        if not self.data:
            return QRectF()
        
        min_x = self.data[0][0] - 1
        max_x = self.data[-1][0] + 1
        
        min_y = min(d[3] for d in self.data)
        max_y = max(d[2] for d in self.data)
        
        return QRectF(min_x, min_y, max_x - min_x, max_y - min_y)

def boot_engine():
    config_manager = ConfigManager()
    main_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "main.py"))
    app_json = PathUtils.get_relative_path(main_path, "config", "app_config.json")
    user_json = PathUtils.get_relative_path(main_path, "config", "user_config.json")
    
    config_manager.load_json(app_json)
    config_manager.load_json(user_json)
    
    app = create_app(config_manager)
    app.boot()
    return app

class EventBridge(QObject):
    market_tick = Signal(dict)

class MainWindow(QMainWindow):
    def __init__(self, engine_app, symbol, interval, limit, replay_speed_ms):
        super().__init__()
        self.setWindowTitle(f"PyQtGraph Backtester - {symbol}")
        self.resize(1024, 768)

        self.engine_app = engine_app
        self.symbol = symbol
        self.interval = interval
        self.limit = limit
        self.replay_speed_ms = replay_speed_ms

        widget = QWidget()
        layout = QVBoxLayout(widget)
        self.setCentralWidget(widget)

        # Initialize pyqtgraph PlotWidget
        pg.setConfigOption('background', '#1E1E1E')
        pg.setConfigOption('foreground', '#FFFFFF')
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setTitle(f"{symbol} Chart")
        self.plot_widget.setLabel('left', 'Price')
        self.plot_widget.setLabel('bottom', 'Time (Index)')
        self.plot_widget.showGrid(x=True, y=True)
        layout.addWidget(self.plot_widget)

        # Add custom candlestick item
        self.candlestick_item = CandlestickItem()
        self.plot_widget.addItem(self.candlestick_item)
        
        self.time_index = 0
        
        self.bridge = EventBridge()
        self.bridge.market_tick.connect(self.on_market_tick_main_thread)
        self.engine_app.event_bus.on(MarketTickEvent, self.on_market_tick_background)

    def start_simulation(self):
        def run_simulation():
            time.sleep(2) 
            command = RunBacktestCommand(
                symbol=self.symbol,
                interval=self.interval,
                limit=self.limit,
                replay_speed_ms=self.replay_speed_ms
            )
            from Binace_Bot.src.application.use_cases.run_backtest import RunBacktestCommandHandler
            handler = self.engine_app.container.resolve(RunBacktestCommandHandler)
            handler.execute(command)
            print("Simulation Thread Finished.")
        
        sim_thread = threading.Thread(target=run_simulation, daemon=True)
        sim_thread.start()

    def on_market_tick_background(self, event: MarketTickEvent):
        if event.market_data.symbol == self.symbol:
            data = {
                "open": event.market_data.open_price,
                "high": event.market_data.high_price,
                "low": event.market_data.low_price,
                "close": event.market_data.close_price,
            }
            self.bridge.market_tick.emit(data)

    @Slot(dict)
    def on_market_tick_main_thread(self, data):
        # X-axis will just be a numeric index for simplicity
        new_candle = (self.time_index, data["open"], data["high"], data["low"], data["close"])
        self.time_index += 1
        
        self.candlestick_item.add_data(new_candle)
        
        # Auto-scroll view
        self.plot_widget.autoRange()

    def closeEvent(self, event):
        print("Chart closed. Shutting down engine...")
        self.engine_app.stop()
        event.accept()

def main():
    engine_app = boot_engine()
    
    qt_app = QApplication(sys.argv)
    
    window = MainWindow(
        engine_app=engine_app,
        symbol="BTCUSDT",
        interval=TimeFrame.ONE_MINUTE,
        limit=500,
        replay_speed_ms=50
    )
    window.show()
    window.start_simulation()
    
    sys.exit(qt_app.exec())

if __name__ == "__main__":
    main()
