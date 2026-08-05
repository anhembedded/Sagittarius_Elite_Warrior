import pyqtgraph as pg
from PySide6 import QtCore, QtGui
from PySide6.QtWidgets import QVBoxLayout
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
            # rect(x, y, w, h)
            # Y is pointing down in QPainter but pyqtgraph handles transforms. 
            # We use bottom-left and width/height.
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
            
    def update_live_candle(self, t: float, o: float, h: float, l: float, c: float):
        """
        @brief Updates the live candle data and requests a minimal repaint.
        """
        # Nếu nến mới xuất hiện (timestamp thay đổi), đẩy nến cũ vào lịch sử và render lại QPicture
        if self.live_candle is not None and t != self.live_candle[0]:
            self.history_data.append(self.live_candle)
            self.generate_picture(self.history_data)
            
        self.live_candle = (t, o, h, l, c)
        self.update() # Only triggers paint(), does NOT rebuild QPicture
        
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


class ChartCard(BaseCard):
    """
    @brief The Chart component for visualizing Candlestick data.
    @details Uses pyqtgraph for Enterprise-grade performance (O(1) Live Updates).
    """
    def __init__(self, symbol: str, parent=None):
        super().__init__(title=f"Live Chart: {symbol}", parent=parent)
        self.symbol = symbol
        self._setup_content()

    def _setup_content(self):
        pg.setConfigOptions(antialias=True)
        
        # Use DateAxisItem for X axis (Unix Timestamp -> Datetime)
        date_axis = pg.DateAxisItem(orientation='bottom')
        
        self.plot_widget = pg.PlotWidget(axisItems={'bottom': date_axis})
        # Match the card background
        self.plot_widget.setBackground('#1e1e24') 
        self.plot_widget.showGrid(x=True, y=True, alpha=0.2)
        
        # Instantiate our High-Performance Candlestick item
        self.candlestick = FastCandlestickItem()
        self.plot_widget.addItem(self.candlestick)
        
        self.body_layout.addWidget(self.plot_widget)

    def set_symbol_title(self, symbol: str) -> None:
        self.symbol = symbol
        self.lbl_title.setText(f"Live Chart: {symbol}")
        
    def render_historical_data(self, data: list[tuple[float, float, float, float, float]]) -> None:
        """
        @brief Render thousands of historical candles instantly.
        @param data List of (timestamp, open, high, low, close)
        """
        self.candlestick.generate_picture(data)
        self.plot_widget.autoRange()
        
    def update_last_candle(self, timestamp: float, open_p: float, high_p: float, low_p: float, close_p: float) -> None:
        """
        @brief Update the live candle in O(1) time complexity.
        """
        self.candlestick.update_live_candle(timestamp, open_p, high_p, low_p, close_p)
        
    def cleanup(self) -> None:
        """
        @brief Garbage collection method. MUST be called before destroying the card.
        """
        self.plot_widget.clear()


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
    
    # Mocking BaseCard Styles for Standalone Testing
    app.setStyleSheet("""
        #base_card { background-color: #1e1e24; border: 1px solid #333333; border-radius: 8px; }
        #base_card_header { background-color: #25252b; padding: 10px; border-bottom: 1px solid #333333; }
        #base_card_title { color: #ffffff; font-weight: bold; font-family: sans-serif; }
    """)
    
    card = ChartCard("BTCUSDT")
    card.resize(900, 500)
    card.show()
    
    print("⏳ Tự động sinh 10,000 nến lịch sử (Historical Data)...")
    now = time.time()
    history = []
    base_price = 60000.0
    
    # 1. MOCK 10,000 CANDLES (O(N) Render via QPicture)
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

    # 2. MOCK LIVE TICK (O(1) Render @ 100ms)
    live_t = now + 60
    live_o = base_price
    live_h = live_o
    live_l = live_o
    live_c = live_o
    
    tick_count = 0
    def on_live_tick():
        global live_t, live_o, live_h, live_l, live_c, tick_count
        
        # Giao động ngẫu nhiên để tạo nến nhấp nháy
        live_c += random.uniform(-10, 10)
        live_h = max(live_h, live_c)
        live_l = min(live_l, live_c)
        
        # Chỉ cập nhật duy nhất 1 nến live
        card.update_last_candle(live_t, live_o, live_h, live_l, live_c)
        
        # Giả lập Rollover (Đóng nến cũ, Mở nến mới) sau mỗi 20 ticks (2 giây)
        tick_count += 1
        if tick_count >= 20:
            tick_count = 0
            live_t += 60 # Chuyển sang phút tiếp theo
            live_o = live_c
            live_h = live_o
            live_l = live_o
            
    timer = QTimer()
    timer.timeout.connect(on_live_tick)
    timer.start(100) # Cập nhật nhấp nháy mỗi 100ms
    print("⚡ Bắn Live Tick 100ms/lần. Cứ 2 giây sẽ sinh ra 1 nến mới để test Rollover Bug!")
    
    sys.exit(app.exec())
