import bisect

import pyqtgraph as pg
from PySide6 import QtCore, QtGui

from . import theme
from .viewport_windowing import visible_slice_indices


class FastCandlestickItem(pg.GraphicsObject):
    """
    @brief Custom PyQtGraph GraphicsObject for rendering candlesticks.

    @details
    Draws only the candles inside the current viewport's visible X range
    (plus a small padding) directly with QPainter in paint(), found via
    O(log N) binary search — NOT a QPicture baked from the full history.

    That QPicture approach was the original design ("O(1) rendering"), but
    profiling a 5000-candle chart showed `QPicture.play()` alone cost ~4.2s
    across 200 simulated pan frames: Qt still has to walk every recorded
    draw command when replaying a QPicture, even the ones clipped outside
    the visible area — caching only skips *rebuilding* the picture, not
    *replaying* the unseen parts of it. Drawing only the visible slice each
    paint() call is O(visible candle count), independent of total history
    size, which is what actually fixes pan/zoom smoothness.
    """

    # Extra margin (in candle-widths) drawn beyond the visible X range so
    # candles don't visibly pop in/out right at the viewport edge.
    _VISIBLE_PADDING_WIDTHS = 2.0

    def __init__(self, data=None):
        pg.GraphicsObject.__init__(self)

        # Colors (Dark Theme)
        self.bull_color = QtGui.QColor(theme.BULL_COLOR)
        self.bear_color = QtGui.QColor(theme.BEAR_COLOR)

        self.candle_width = 20.0  # Default width, updated dynamically
        self.live_candle = None  # Holds (t, o, h, l, c) for the live tick
        self.history_data = []  # Tracks all historical data
        self._full_bounds_rect = QtCore.QRectF()
        self._cached_visible_bounds = None  # (lo, hi, min_y, max_y)

        if data:
            self.history_data = list(data)
            self.generate_picture(self.history_data)

    def generate_picture(self, data: list[tuple[float, float, float, float, float]]):
        """
        @brief Recomputes candle_width and the cached full-history bounding
        rect for new/updated data. O(N) — called once per historical load
        or closed candle, not per paint/pan frame (see class docstring for
        why no picture is baked here anymore).
        @details Stores its own copy of `data` — callers (e.g. ChartCard, which
        owns `_raw_history`) must be able to independently append to their own
        list without silently duplicating entries in this cache's `history_data`
        (and vice versa).
        """
        if data is not self.history_data:
            self.history_data = list(data)

        # Dynamically calculate candle width from the time interval between
        # candles. Uses the MEDIAN gap across the whole series, not just
        # data[1]-data[0] — a single anomalous first gap (e.g. a missing
        # candle / exchange downtime right at the start of the loaded
        # history) used to miscalibrate the width for every candle in the
        # chart, making them render far too wide (overlapping into a solid
        # block) or too thin. The median is robust to a few such outliers.
        # abs() guards against a negative width if `data` were ever
        # descending (would otherwise make candles vanish — see
        # boundingRect/dataBounds, which assume ascending time).
        # Qt requires prepareGeometryChange() to be called *before* changing state
        # that alters boundingRect(), so it can cleanly remove the old bounds
        # from the scene's BSP tree before inserting the new ones.
        self.prepareGeometryChange()

        if len(data) > 1:
            gaps = sorted(data[i + 1][0] - data[i][0] for i in range(len(data) - 1))
            median_gap = gaps[len(gaps) // 2]
            self.candle_width = abs(median_gap) / 3.0

        self._recompute_full_bounds()
        # A full data replacement (render_historical_data/prepend_historical_data/
        # set_chart_type) can land on the same visible (lo, hi) index window as
        # before (e.g. "last 150 candles" after a symbol/timeframe switch) even
        # though history_data itself is now entirely different — dataBounds()'s
        # cache is keyed only by (lo, hi), so without this it would keep
        # returning the PREVIOUS dataset's min/max Y, feeding the ViewBox a
        # stale auto-range while paint() draws the new candles (bug: chart
        # shows no visible candlesticks / wrong Y-axis scale after a reload).
        self._cached_visible_bounds = None
        self.informViewBoundsChanged()
        self.update()

    def _recompute_full_bounds(self) -> None:
        """Caches the full-history bounding rect (used by boundingRect(),
        which Qt calls frequently) so it doesn't need an O(N) min/max scan
        on every call — only recomputed here, when data actually changes."""
        if not self.history_data:
            self._full_bounds_rect = QtCore.QRectF()
            return
        w = self.candle_width
        min_t = self.history_data[0][0] - w
        max_t = self.history_data[-1][0] + w
        min_y = min(row[3] for row in self.history_data)
        max_y = max(row[2] for row in self.history_data)
        self._full_bounds_rect = QtCore.QRectF(
            min_t, min_y, max_t - min_t, max_y - min_y
        )

    def _visible_history_slice(self) -> list[tuple[float, float, float, float, float]]:
        """
        @brief Returns the history_data slice inside the current viewport's
        X range (+ padding), via O(log N) binary search.
        @details Falls back to the full history if this item isn't attached
        to a ViewBox yet (e.g. under a unit test that never adds it to a
        scene) — correctness over the perf fast-path in that edge case.
        """
        view_box = self.getViewBox()
        if view_box is None or not self.history_data:
            return self.history_data

        (min_x, max_x), _ = view_box.viewRange()
        padding = self.candle_width * self._VISIBLE_PADDING_WIDTHS
        lo, hi = visible_slice_indices(
            self.history_data, min_x, max_x, padding, key=lambda row: row[0]
        )
        return self.history_data[lo:hi]

    def paint(self, p: QtGui.QPainter, *args):
        """
        @brief Draws only the currently-visible candles (+ padding), plus
        the live candle. O(visible count), not O(total history) — see
        class docstring.
        """
        bull_brush = pg.mkBrush(self.bull_color)
        bull_pen = pg.mkPen(self.bull_color)
        bear_brush = pg.mkBrush(self.bear_color)
        bear_pen = pg.mkPen(self.bear_color)

        bull_lines = []
        bull_rects = []
        bear_lines = []
        bear_rects = []

        for t, o, h, low, c in self._visible_history_slice():
            line = QtCore.QLineF(t, low, t, h)
            # Draw body (Width is drawn outward from center t)
            # Use min/abs to strictly enforce positive height to prevent Qt drawRect anti-aliasing bugs
            rect = QtCore.QRectF(
                t - self.candle_width, min(o, c), self.candle_width * 2, abs(c - o)
            )

            if c >= o:
                bull_lines.append(line)
                bull_rects.append(rect)
            else:
                bear_lines.append(line)
                bear_rects.append(rect)

        # Draw the live (in-progress) candle, always — it's a single item.
        if self.live_candle:
            t, o, h, low, c = self.live_candle
            line = QtCore.QLineF(t, low, t, h)
            rect = QtCore.QRectF(
                t - self.candle_width, min(o, c), self.candle_width * 2, abs(c - o)
            )
            if c >= o:
                bull_lines.append(line)
                bull_rects.append(rect)
            else:
                bear_lines.append(line)
                bear_rects.append(rect)

        # Batch draw bull candles
        p.setPen(bull_pen)
        p.setBrush(bull_brush)
        p.drawLines(bull_lines)
        p.drawRects(bull_rects)

        # Batch draw bear candles
        p.setPen(bear_pen)
        p.setBrush(bear_brush)
        p.drawLines(bear_lines)
        p.drawRects(bear_rects)

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

        # Recompute width + cached bounds only — no picture to rebuild
        # anymore (fast enough for once per minute either way).
        self.generate_picture(self.history_data)

        # Reset live candle state so a new one can form
        self.live_candle = None
        self.update()

    def get_ohlc_at(self, x: float) -> tuple[float, float, float, float, float] | None:
        """
        @brief Returns the (t, o, h, l, c) candle nearest to x, for crosshair OHLC readouts.
        @details O(log N) via bisect on history_data (assumed ascending-sorted by time —
        the same invariant generate_picture()'s width calculation relies on). Panning is a
        mouse-move gesture, so this fires on every 60fps-throttled crosshair update *during*
        a drag, same as dataBounds() below — an O(N) scan here (the old approach) was a
        second, compounding source of the pan/drag stutter fixed by this class's dataBounds.
        """
        if not self.history_data:
            return self.live_candle

        idx = bisect.bisect_left(self.history_data, x, key=lambda row: row[0])
        if idx <= 0:
            nearest = self.history_data[0]
        elif idx >= len(self.history_data):
            nearest = self.history_data[-1]
        else:
            before, after = self.history_data[idx - 1], self.history_data[idx]
            nearest = before if (x - before[0]) <= (after[0] - x) else after

        if self.live_candle and abs(self.live_candle[0] - x) < abs(nearest[0] - x):
            return self.live_candle
        return nearest

    def boundingRect(self) -> QtCore.QRectF:
        """
        @brief Calculates the bounding box for Qt's rendering engine.
        @details O(1) — reads the cached full-history rect (see
        _recompute_full_bounds) instead of scanning history_data, since Qt
        can call this frequently.
        """
        rect = QtCore.QRectF(self._full_bounds_rect)

        if self.live_candle:
            t, _o, h, low, _c = self.live_candle
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

                # pyqtgraph's ViewBox calls dataBounds(ax=1, orthoRange=...) to
                # re-autoscale Y on EVERY range-changed event — which fires
                # continuously while the user drags/pans, not just on zoom.
                # An O(N) scan over the full history here (the old approach)
                # was one cause of visible pan/drag stutter with a few
                # thousand candles loaded: bisect narrows to the visible
                # slice in O(log N) first. Furthermore, we cache the result
                # by window indices (lo, hi) to prevent re-scanning the visible
                # slice continuously on sub-pixel/same-candle pan boundaries.
                lo, hi = visible_slice_indices(
                    self.history_data, min_x, max_x, key=lambda row: row[0]
                )

                # Use cache if valid
                if (
                    self._cached_visible_bounds
                    and self._cached_visible_bounds[0] == lo
                    and self._cached_visible_bounds[1] == hi
                ):
                    cached_min_y, cached_max_y = (
                        self._cached_visible_bounds[2],
                        self._cached_visible_bounds[3],
                    )
                else:
                    visible = self.history_data[lo:hi]
                    if visible:
                        cached_min_y = min(row[3] for row in visible)
                        cached_max_y = max(row[2] for row in visible)
                        self._cached_visible_bounds = (
                            lo,
                            hi,
                            cached_min_y,
                            cached_max_y,
                        )
                    else:
                        cached_min_y, cached_max_y = None, None
                        self._cached_visible_bounds = (lo, hi, None, None)

                min_y, max_y = cached_min_y, cached_max_y

                if self.live_candle and min_x <= self.live_candle[0] <= max_x:
                    live_low = self.live_candle[3]
                    live_high = self.live_candle[2]
                    min_y = min(min_y, live_low) if min_y is not None else live_low
                    max_y = max(max_y, live_high) if max_y is not None else live_high

                if min_y is not None and max_y is not None:
                    return [min_y, max_y]

            # Fallback to global bounds (O(1) using cached rect, avoids O(N) fallback scan)
            min_y, max_y = None, None
            if self._full_bounds_rect and self._full_bounds_rect.isValid():
                min_y = self._full_bounds_rect.top()
                max_y = self._full_bounds_rect.bottom()
            elif self.history_data:
                # Fallback if somehow called before bounds rect generated
                min_y = min(row[3] for row in self.history_data)
                max_y = max(row[2] for row in self.history_data)

            if self.live_candle:
                min_y = (
                    min(min_y, self.live_candle[3])
                    if min_y is not None
                    else self.live_candle[3]
                )
                max_y = (
                    max(max_y, self.live_candle[2])
                    if max_y is not None
                    else self.live_candle[2]
                )

            if min_y is not None and max_y is not None:
                return [min_y, max_y]

        return [None, None]
