import pyqtgraph as pg
from PySide6 import QtCore, QtGui

from . import theme


class FastCandlestickItem(pg.GraphicsObject):
    """
    @brief Custom PyQtGraph GraphicsObject for rendering O(1) candlesticks.
    @details Uses QPicture for historical caching and manual paint for live updates.
    """

    def __init__(self, data=None):
        pg.GraphicsObject.__init__(self)
        self.picture = QtGui.QPicture()

        # Colors (Dark Theme)
        self.bull_color = QtGui.QColor(theme.BULL_COLOR)
        self.bear_color = QtGui.QColor(theme.BEAR_COLOR)

        self.candle_width = 20.0  # Default width, updated dynamically
        self.live_candle = None  # Holds (t, o, h, l, c) for the live tick
        self.history_data = []  # Tracks all historical data

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

        for t, o, h, low, c in data:
            if c >= o:
                p.setPen(bull_pen)
                p.setBrush(bull_brush)
            else:
                p.setPen(bear_pen)
                p.setBrush(bear_brush)

            # Draw wick
            p.drawLine(QtCore.QPointF(t, low), QtCore.QPointF(t, h))

            # Draw body (Width is drawn outward from center t)
            # Use min/abs to strictly enforce positive height to prevent Qt drawRect anti-aliasing bugs
            rect = QtCore.QRectF(
                t - self.candle_width, min(o, c), self.candle_width * 2, abs(c - o)
            )
            p.drawRect(rect)

        p.end()
        self.prepareGeometryChange()
        self.informViewBoundsChanged()
        self.update()

    def paint(self, p: QtGui.QPainter, *args):
        """
        @brief O(1) rendering method. Draws historical cache + live candle.
        """
        # 1. Draw 10,000+ cached historical candles instantly
        p.drawPicture(0, 0, self.picture)

        # 2. Draw ONLY the last live candle dynamically
        if self.live_candle:
            t, o, h, low, c = self.live_candle
            if c >= o:
                p.setPen(pg.mkPen(self.bull_color))
                p.setBrush(pg.mkBrush(self.bull_color))
            else:
                p.setPen(pg.mkPen(self.bear_color))
                p.setBrush(pg.mkBrush(self.bear_color))

            p.drawLine(QtCore.QPointF(t, low), QtCore.QPointF(t, h))
            # Use min/abs to strictly enforce positive height
            rect = QtCore.QRectF(
                t - self.candle_width, min(o, c), self.candle_width * 2, abs(c - o)
            )
            p.drawRect(rect)

    def update_live_candle(
        self,
        timestamp: float,
        open_p: float,
        high_p: float,
        low_p: float,
        close_p: float,
    ) -> None:
        self.live_candle = (timestamp, open_p, high_p, low_p, close_p)
        self.update()

    def append_closed_candle(
        self,
        timestamp: float,
        open_p: float,
        high_p: float,
        low_p: float,
        close_p: float,
    ) -> None:
        """
        @brief Explicitly push a closed candle into the historical cache.
        """
        closed_candle = (timestamp, open_p, high_p, low_p, close_p)
        self.history_data.append(closed_candle)

        # O(1) Re-cache the entire history (fast enough for once per minute)
        self.generate_picture(self.history_data)

        # Reset live candle state so a new one can form
        self.live_candle = None
        self.update()  # Only triggers paint(), does NOT rebuild QPicture

    def get_ohlc_at(self, x: float) -> tuple[float, float, float, float, float] | None:
        """
        @brief Returns the (t, o, h, l, c) candle nearest to x, for crosshair OHLC readouts.
        @details O(N) nearest-timestamp scan — acceptable at hover-throttled (60fps) rates,
        consistent with the O(N) bounds lookups already used elsewhere in this class.
        """
        candidates = list(self.history_data)
        if self.live_candle:
            candidates.append(self.live_candle)
        if not candidates:
            return None
        return min(candidates, key=lambda candle: abs(candle[0] - x))

    def boundingRect(self) -> QtCore.QRectF:
        """
        @brief Calculates the bounding box for Qt's rendering engine.
        """
        rect = QtCore.QRectF(self.picture.boundingRect())

        if self.live_candle:
            t, o, h, low, c = self.live_candle
            w = self.candle_width
            # Height spans from low to high
            live_rect = QtCore.QRectF(t - w, low, w * 2, h - low)
            rect = rect.united(live_rect)

        return rect

    def dataBounds(self, ax, frac=1.0, orthoRange=None):
        """
        @brief Required by ViewBox to auto-scale Y axis based on visible X range (TradingView style).
        """
        if ax == 0:
            if not self.history_data and not self.live_candle:
                return [None, None]
            min_x = (
                self.history_data[0][0] if self.history_data else self.live_candle[0]
            )
            max_x = (
                self.history_data[-1][0] if self.history_data else self.live_candle[0]
            )
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
                visible_lows = [
                    low
                    for (t, o, h, low, c) in self.history_data
                    if min_x <= t <= max_x
                ]
                visible_highs = [
                    h for (t, o, h, low, c) in self.history_data if min_x <= t <= max_x
                ]

                if self.live_candle and min_x <= self.live_candle[0] <= max_x:
                    visible_lows.append(self.live_candle[3])
                    visible_highs.append(self.live_candle[2])

                if visible_lows and visible_highs:
                    return [min(visible_lows), max(visible_highs)]

            # Fallback to global bounds
            all_lows = [low for (_, _, _, low, _) in self.history_data]
            all_highs = [h for (_, _, h, _, _) in self.history_data]
            if self.live_candle:
                all_lows.append(self.live_candle[3])
                all_highs.append(self.live_candle[2])

            if all_lows and all_highs:
                return [min(all_lows), max(all_highs)]

        return [None, None]
