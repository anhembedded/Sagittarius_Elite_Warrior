import pyqtgraph as pg

from . import theme
from .viewport_windowing import visible_slice_indices

_DEFAULT_BAR_WIDTH = 13.33
# Extra margin (in bar-widths) applied beyond the visible X range so bars
# don't visibly pop in/out right at the viewport edge — mirrors
# FastCandlestickItem._VISIBLE_PADDING_WIDTHS.
_VISIBLE_PADDING_WIDTHS = 2.0


class VolumeItem:
    """
    @brief Renders a TradingView-style volume histogram, colored by candle direction.
    @details Mirrors FastCandlestickItem's historical/live-tick lifecycle. Keeps the
    full series in `_timestamps`/`_heights`/`_colors`, but only pushes the bars inside
    the last-known visible X range to pyqtgraph's BarGraphItem via `refresh_window()`
    (called by ChartCard on every pan/zoom) — pushing the full history to setOpts() on
    every such change was a real cost once a few thousand candles were loaded, same
    category of issue fixed in FastCandlestickItem (see its docstring).
    """

    def __init__(self) -> None:
        self._bar_width = _DEFAULT_BAR_WIDTH
        self._timestamps: list[float] = []
        self._heights: list[float] = []
        self._colors: list[str] = []
        self._live_index: int | None = None
        self._visible_range: tuple[float, float] | None = None

        self.graphics_item = pg.BarGraphItem(
            x=[], height=[], width=self._bar_width, brushes=[]
        )

    def render_historical(self, data: list[tuple[float, float, bool]]) -> None:
        """@param data: list of (timestamp, volume, is_bullish)."""
        if len(data) > 1:
            self._bar_width = (data[1][0] - data[0][0]) / 1.5

        self._timestamps = [row[0] for row in data]
        self._heights = [row[1] for row in data]
        self._colors = [
            theme.BULL_COLOR if row[2] else theme.BEAR_COLOR for row in data
        ]
        self._live_index = None
        self._apply()

    def as_tuples(self) -> list[tuple[float, float, bool]]:
        """@brief Reconstructs the (timestamp, volume, is_bullish) rows
        render_historical() was built from (BOT-035) — lets a caller combine
        older + already-loaded volume before a wholesale re-render, without
        this class needing to know anything about prepending itself."""
        return [
            (t, h, c == theme.BULL_COLOR)
            for t, h, c in zip(self._timestamps, self._heights, self._colors)
        ]

    def update_live(self, timestamp: float, volume: float, is_bullish: bool) -> None:
        color = theme.BULL_COLOR if is_bullish else theme.BEAR_COLOR
        if self._live_index is None:
            self._timestamps.append(timestamp)
            self._heights.append(volume)
            self._colors.append(color)
            self._live_index = len(self._timestamps) - 1
        else:
            self._timestamps[self._live_index] = timestamp
            self._heights[self._live_index] = volume
            self._colors[self._live_index] = color
        self._apply()

    def append_closed(self, timestamp: float, volume: float, is_bullish: bool) -> None:
        """Finalizes the live bar into permanent history so the next tick starts a new one."""
        self.update_live(timestamp, volume, is_bullish)
        self._live_index = None

    def refresh_window(self, min_x: float, max_x: float) -> None:
        """
        @brief Re-applies just the bars inside the visible X range (+ padding)
        to the underlying BarGraphItem, via O(log N) binary search.
        @details Called by ChartCard whenever the chart's viewport changes
        (pan/zoom). Remembers the range so subsequent data updates
        (update_live/append_closed) stay windowed too, without ChartCard
        having to re-call this on every single tick.
        """
        self._visible_range = (min_x, max_x)
        self._apply()

    def _apply(self) -> None:
        if self._visible_range is not None:
            min_x, max_x = self._visible_range
            padding = self._bar_width * _VISIBLE_PADDING_WIDTHS
            lo, hi = visible_slice_indices(self._timestamps, min_x, max_x, padding)
        else:
            lo, hi = 0, len(self._timestamps)

        self.graphics_item.setOpts(
            x=self._timestamps[lo:hi],
            height=self._heights[lo:hi],
            width=self._bar_width,
            brushes=[pg.mkBrush(c) for c in self._colors[lo:hi]],
        )
