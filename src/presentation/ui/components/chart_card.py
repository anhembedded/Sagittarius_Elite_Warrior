import pyqtgraph as pg
from PySide6 import QtCore, QtGui
from PySide6.QtWidgets import QVBoxLayout
from datetime import datetime, timezone
from Binace_Bot.src.presentation.ui.components.base_card import BaseCard

class FastCandlestickItem(pg.GraphicsObject):
    """
    @brief Custom PyQtGraph GraphicsObject for rendering O(1) candlesticks.
    @details Uses QPicture for historical caching and manual paint for live updates.
    """
    def __init__(self, data=None):
        pg.GraphicsObject.__init__(self)
        self.picture = QtGui.QPicture()
        
        # Colors (Dark Theme)
        self.bull_color = QtGui.QColor("#26a69a")
        self.bear_color = QtGui.QColor("#ef5350")
        
        self.candle_width = 20.0 # Default width, updated dynamically
        self.live_candle = None # Holds (t, o, h, l, c) for the live tick
        self.history_data = [] # Tracks all historical data
        
        if data:
            self.history_data = data
            self.generate_picture(data)
            
    def generate_picture(self, data: list[tuple[float, float, float, float, float]]):
        """
        @brief Generates a cached QPicture for historical data. O(N) complexity once.
        """
        self.history_data = data
        self.picture = QtGui.QPicture()
        p = QtGui.QPainter(self.picture)
        
        bull_brush = pg.mkBrush(self.bull_color)
        bull_pen = pg.mkPen(self.bull_color)
        bear_brush = pg.mkBrush(self.bear_color)
        bear_pen = pg.mkPen(self.bear_color)
        
        # Dynamically calculate candle width based on the time interval between candles
        if len(data) > 1:
            self.candle_width = (data[1][0] - data[0][0]) / 3.0
            
        for (t, o, h, l, c) in data:
            if c >= o:
                p.setPen(bull_pen)
                p.setBrush(bull_brush)
            else:
                p.setPen(bear_pen)
                p.setBrush(bear_brush)
                
            # Draw wick
            p.drawLine(QtCore.QPointF(t, l), QtCore.QPointF(t, h))
            
            # Draw body (Width is drawn outward from center t)
            rect = QtCore.QRectF(t - self.candle_width, o, self.candle_width * 2, c - o)
            p.drawRect(rect)
            
        p.end()
        self.prepareGeometryChange()
        self.informViewBoundsChanged()
        
    def paint(self, p: QtGui.QPainter, *args):
        """
        @brief O(1) rendering method. Draws historical cache + live candle.
        """
        # 1. Draw 10,000+ cached historical candles instantly
        p.drawPicture(0, 0, self.picture)
        
        # 2. Draw ONLY the last live candle dynamically
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
            
    def update_live_candle(self, timestamp: float, open_p: float, high_p: float, low_p: float, close_p: float) -> None:
        self.live_candle = (timestamp, open_p, high_p, low_p, close_p)
        self.update() 
        
    def append_closed_candle(self, timestamp: float, open_p: float, high_p: float, low_p: float, close_p: float) -> None:
        """
        @brief Explicitly push a closed candle into the historical cache.
        """
        closed_candle = (timestamp, open_p, high_p, low_p, close_p)
        self.history_data.append(closed_candle)
        
        # O(1) Re-cache the entire history (fast enough for once per minute)
        self.generate_picture(self.history_data)
        
        # Reset live candle state so a new one can form
        self.live_candle = None
        self.update()# Only triggers paint(), does NOT rebuild QPicture
        
    def boundingRect(self) -> QtCore.QRectF:
        """
        @brief Calculates the bounding box for Qt's rendering engine.
        """
        rect = QtCore.QRectF(self.picture.boundingRect())
        
        if self.live_candle:
            t, o, h, l, c = self.live_candle
            w = self.candle_width
            # Height spans from low to high
            live_rect = QtCore.QRectF(t - w, l, w * 2, h - l)
            rect = rect.united(live_rect)
            
        return rect
        
    def dataBounds(self, ax, frac=1.0, orthoRange=None):
        """
        @brief Required by ViewBox to auto-scale Y axis based on visible X range (TradingView style).
        """
        if ax == 0:
            if not self.history_data and not self.live_candle:
                return [None, None]
            min_x = self.history_data[0][0] if self.history_data else self.live_candle[0]
            max_x = self.history_data[-1][0] if self.history_data else self.live_candle[0]
            if self.live_candle and self.live_candle[0] > max_x:
                max_x = self.live_candle[0]
            return [min_x, max_x]
            
        elif ax == 1:
            if not self.history_data and not self.live_candle:
                return [None, None]
                
            # Calculate Y bounds based ONLY on the visible X range
            if orthoRange is not None:
                min_x, max_x = orthoRange
                
                # O(N) lookup for visible candles. For 10k candles, this takes < 1ms.
                visible_lows = [l for (t, o, h, l, c) in self.history_data if min_x <= t <= max_x]
                visible_highs = [h for (t, o, h, l, c) in self.history_data if min_x <= t <= max_x]
                
                if self.live_candle and min_x <= self.live_candle[0] <= max_x:
                    visible_lows.append(self.live_candle[3])
                    visible_highs.append(self.live_candle[2])
                    
                if visible_lows and visible_highs:
                    return [min(visible_lows), max(visible_highs)]
            
            # Fallback to global bounds
            all_lows = [l for (_, _, _, l, _) in self.history_data]
            all_highs = [h for (_, _, h, _, _) in self.history_data]
            if self.live_candle:
                all_lows.append(self.live_candle[3])
                all_highs.append(self.live_candle[2])
                
            if all_lows and all_highs:
                return [min(all_lows), max(all_highs)]
                
        return [None, None]


class ChartCard(BaseCard):
    """
    @brief The Chart component for visualizing Candlestick data & Extensible Technical Indicators.
    @details Uses GraphicsLayoutWidget for Multi-plot support and SignalProxy for high-performance crosshairs.
    """
    def __init__(self, symbol: str, parent=None):
        super().__init__(title=f"Live Chart: {symbol}", parent=parent)
        self.symbol = symbol
        self.indicators = {}
        self.sub_plots = []
        self.plots = [] # Stores all PlotItems (Main + Sub)
        self.v_lines = []
        self.h_lines = []
        self._setup_content()

    def _setup_content(self):
        pg.setConfigOptions(antialias=True)
        
        self.layout_widget = pg.GraphicsLayoutWidget()
        self.layout_widget.setBackground('#1e1e24')
        self.body_layout.addWidget(self.layout_widget)
        
        # Crosshair Info Label (Row 0)
        self.lbl_crosshair = self.layout_widget.addLabel(
            "<span style='color: #888888; font-size: 11px;'>Hover to see data</span>", 
            row=0, col=0, justify="right"
        )
        
        # Main Plot (Row 1)
        date_axis = pg.DateAxisItem(orientation='bottom')
        self.main_plot = self.layout_widget.addPlot(row=1, col=0, axisItems={'bottom': date_axis})
        self.main_plot.showGrid(x=True, y=True, alpha=0.2)
        
        # Enable TradingView style: Scroll zooms X, Y auto-scales to visible X
        # Cho phép tương tác chuột trên cả 2 trục để có thể kéo (pan/scale) trục Y
        self.main_plot.setMouseEnabled(x=True, y=True) 
        self.main_plot.vb.setAutoVisible(y=True)
        self.main_plot.vb.enableAutoRange(axis='y', enable=True)
        
        # Candlestick Object
        self.candlestick = FastCandlestickItem()
        self.main_plot.addItem(self.candlestick)
        self._current_row = 2
        
        self._register_plot(self.main_plot)
        
        # Setup High-Performance Throttled Mouse Proxy (60 fps limit)
        self.proxy = pg.SignalProxy(
            self.layout_widget.scene().sigMouseMoved, 
            rateLimit=60, 
            slot=self._mouse_moved
        )

    def _register_plot(self, plot: pg.PlotItem):
        """Helper to register a plot and attach crosshair lines to it."""
        self.plots.append(plot)
        
        v_line = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen(color='#555555', style=QtCore.Qt.DashLine))
        h_line = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen(color='#555555', style=QtCore.Qt.DashLine))
        
        v_line.hide()
        h_line.hide()
        
        plot.addItem(v_line, ignoreBounds=True)
        plot.addItem(h_line, ignoreBounds=True)
        
        self.v_lines.append(v_line)
        self.h_lines.append(h_line)

    def _mouse_moved(self, evt):
        """
        @brief Throttled slot for handling crosshair tracking cleanly.
        """
        pos = evt[0]

        hovered_plot = None
        for i, plot in enumerate(self.plots):
            if plot.sceneBoundingRect().contains(pos):
                hovered_plot = plot
                
                # Convert screen coordinates to plot data coordinates
                mouse_point = plot.vb.mapSceneToView(pos)
                x_val = mouse_point.x()
                y_val = mouse_point.y()
                
                # Show & update horizontal line ONLY for the hovered plot
                self.h_lines[i].setPos(y_val)
                self.h_lines[i].show()
                
                # Update ALL vertical lines across all plots to stay in sync
                for v_line in self.v_lines:
                    v_line.setPos(x_val)
                    v_line.show()
                
                # Update global label cleanly
                dt_str = datetime.fromtimestamp(x_val, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                # Clean HTML for pyqtgraph label
                self.lbl_crosshair.setText(
                    f"<span style='color: #aaaaaa'>Time:</span> <span style='color: #ffffff'>{dt_str}</span> | "
                    f"<span style='color: #aaaaaa'>Value:</span> <span style='color: #26a69a'>{y_val:.4f}</span>"
                )
            else:
                self.h_lines[i].hide()
                
        if not hovered_plot:
            for v_line in self.v_lines:
                v_line.hide()
            self.lbl_crosshair.setText("Hover to see data")

    # ==========================================
    # PUBLIC API FOR PRESENTER
    # ==========================================
    def set_symbol_title(self, symbol: str) -> None:
        self.symbol = symbol
        self.lbl_title.setText(f"Live Chart: {symbol}")
        
    def render_historical_data(self, data: list[tuple[float, float, float, float, float]]) -> None:
        self.candlestick.generate_picture(data)
        self.main_plot.autoRange()
        
    def update_last_candle(self, timestamp: float, open_p: float, high_p: float, low_p: float, close_p: float) -> None:
        self.candlestick.update_live_candle(timestamp, open_p, high_p, low_p, close_p)
        
    def append_closed_candle(self, timestamp: float, open_p: float, high_p: float, low_p: float, close_p: float) -> None:
        self.candlestick.append_closed_candle(timestamp, open_p, high_p, low_p, close_p)
        
    def add_overlay_indicator(self, name: str, color: str) -> None:
        """Adds a line indicator on top of the main candlestick plot (e.g. SMA)"""
        curve = self.main_plot.plot(pen=pg.mkPen(color=color, width=2), name=name)
        self.indicators[name] = curve

    def add_subplot_indicator(self, name: str, color: str, height_ratio: int = 1) -> None:
        """Adds a separate subplot below the main chart (e.g. RSI, MACD, Volume)"""
        # Create a new X-axis but hide it to keep UI clean, we use the main plot's axis
        sub_plot = self.layout_widget.addPlot(row=self._current_row, col=0)
        sub_plot.showGrid(x=True, y=True, alpha=0.2)
        sub_plot.setXLink(self.main_plot)
        
        # Adjust vertical spacing ratios
        self.layout_widget.ci.layout.setRowStretchFactor(1, 3) # Main plot stretch
        self.layout_widget.ci.layout.setRowStretchFactor(self._current_row, height_ratio)
        
        curve = sub_plot.plot(pen=pg.mkPen(color=color, width=2), name=name)
        self.indicators[name] = curve
        self.sub_plots.append(sub_plot)
        self._register_plot(sub_plot)
        
        self._current_row += 1

    def update_indicator_data(self, name: str, x_data: list[float], y_data: list[float]) -> None:
        """Updates the data arrays for a specific indicator."""
        curve = self.indicators.get(name)
        if curve:
            curve.setData(x=x_data, y=y_data)

    def cleanup(self) -> None:
        """
        @brief Garbage collection method. Strict cleanup of C++ bindings.
        """
        if hasattr(self, 'proxy') and self.proxy:
            self.proxy.disconnect()
            self.proxy = None
            
        self.indicators.clear()
        self.sub_plots.clear()
        self.plots.clear()
        self.v_lines.clear()
        self.h_lines.clear()
        
        self.layout_widget.clear()


# ==========================================
# 🧪 INDEPENDENT COMPONENT TESTING
# ==========================================
if __name__ == "__main__":
    import sys
    import time
    import random
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QTimer

    app = QApplication(sys.argv)
    
    app.setStyleSheet("""
        #base_card { background-color: #1e1e24; border: 1px solid #333333; border-radius: 8px; }
        #base_card_header { background-color: #25252b; padding: 10px; border-bottom: 1px solid #333333; }
        #base_card_title { color: #ffffff; font-weight: bold; font-family: sans-serif; }
    """)
    
    card = ChartCard("BTCUSDT")
    card.resize(1000, 700)
    card.show()
    
    print("⏳ Tự động sinh 5,000 nến lịch sử và 2 Indicators (SMA, RSI)...")
    now = time.time()
    history = []
    sma_x, sma_y = [], []
    rsi_x, rsi_y = [], []
    
    base_price = 60000.0
    
    # 1. SETUP INDICATORS
    card.add_overlay_indicator("SMA_20", color="#f39c12")
    card.add_subplot_indicator("RSI_14", color="#9b59b6", height_ratio=1)
    
    # 2. MOCK 5,000 CANDLES + INDICATOR DATA
    for i in range(5000):
        t = now - (5000 - i) * 60
        o = base_price
        c = o + random.uniform(-100, 100)
        h = max(o, c) + random.uniform(0, 50)
        l = min(o, c) - random.uniform(0, 50)
        history.append((t, o, h, l, c))
        base_price = c
        
        # Giả lập data cho SMA và RSI
        sma_x.append(t)
        sma_y.append(c + random.uniform(-50, 50))
        
        rsi_x.append(t)
        rsi_y.append(50 + random.uniform(-20, 20))
        
    card.render_historical_data(history)
    card.update_indicator_data("SMA_20", sma_x, sma_y)
    card.update_indicator_data("RSI_14", rsi_x, rsi_y)
    print("✅ Đã load xong bộ khung Main Chart & Subplots.")

    # 3. MOCK LIVE TICK
    live_t = now + 60
    live_o = base_price
    live_h = live_o
    live_l = live_o
    live_c = live_o
    
    tick_count = 0
    def on_live_tick():
        global live_t, live_o, live_h, live_l, live_c, tick_count
        
        live_c += random.uniform(-10, 10)
        live_h = max(live_h, live_c)
        live_l = min(live_l, live_c)
        card.update_last_candle(live_t, live_o, live_h, live_l, live_c)
        
        # Cập nhật đuôi (tail) của mảng Indicator
        sma_x[-1] = live_t
        sma_y[-1] = live_c
        rsi_x[-1] = live_t
        rsi_y[-1] = 50 + random.uniform(-5, 5)
        
        card.update_indicator_data("SMA_20", sma_x, sma_y)
        card.update_indicator_data("RSI_14", rsi_x, rsi_y)
        
        tick_count += 1
        if tick_count >= 20:
            tick_count = 0
            live_t += 60 
            live_o = live_c
            live_h = live_o
            live_l = live_o
            
            # Thêm điểm mới vào mảng
            sma_x.append(live_t)
            sma_y.append(live_c)
            rsi_x.append(live_t)
            rsi_y.append(50)
            
    timer = QTimer()
    timer.timeout.connect(on_live_tick)
    timer.start(100)
    
    sys.exit(app.exec())
