import pyqtgraph as pg

from . import theme
from .chart_lod import (
    aggregate_volume_bucket,
    build_volume_lod_pyramid,
    lod_slice_indices,
    select_lod_level,
)
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

    def __init__(self, *, lod_enabled: bool = True) -> None:
        self._bar_width = _DEFAULT_BAR_WIDTH
        self._lod_enabled = bool(lod_enabled)
        self._timestamps: list[float] = []
        self._heights: list[float] = []
        self._brushes: list[pg.QtGui.QBrush] = []
        self._bull_brush = pg.mkBrush(theme.BULL_COLOR)
        self._bear_brush = pg.mkBrush(theme.BEAR_COLOR)
        self._live_index: int | None = None
        self._lod_levels: list[list[tuple[float, float, bool]]] = [[]]
        self._visible_range: tuple[float, float] | None = None
        self._data_revision = 0
        self._last_applied_signature: tuple[int, int, int, float, int] | None = None
        self.applied_update_count = 0
        self.last_applied_lod_level = 0
        self.last_applied_bar_count = 0

        self.graphics_item = pg.BarGraphItem(
            x=[], height=[], width=self._bar_width, brushes=[]
        )

    def render_historical(self, data: list[tuple[float, float, bool]]) -> None:
        """@param data: list of (timestamp, volume, is_bullish)."""
        if len(data) > 1:
            self._bar_width = (data[1][0] - data[0][0]) / 1.5

        self._timestamps = [row[0] for row in data]
        self._heights = [row[1] for row in data]
        self._brushes = [
            self._bull_brush if row[2] else self._bear_brush for row in data
        ]
        self._lod_levels = build_volume_lod_pyramid(data)
        self._live_index = None
        self._data_revision += 1
        self._apply()

    def as_tuples(self) -> list[tuple[float, float, bool]]:
        """@brief Reconstructs the (timestamp, volume, is_bullish) rows
        render_historical() was built from (BOT-035) — lets a caller combine
        older + already-loaded volume before a wholesale re-render, without
        this class needing to know anything about prepending itself."""
        return [
            (t, h, b == self._bull_brush)
            for t, h, b in zip(self._timestamps, self._heights, self._brushes)
        ]

    def update_live(self, timestamp: float, volume: float, is_bullish: bool) -> None:
        brush = self._bull_brush if is_bullish else self._bear_brush
        if self._live_index is not None and self._live_index < len(self._timestamps):
            self._timestamps[self._live_index] = timestamp
            self._heights[self._live_index] = volume
            self._brushes[self._live_index] = brush
            self._update_lod_tail((timestamp, volume, is_bullish), append=False)
        elif self._timestamps and self._timestamps[-1] == timestamp:
            self._live_index = len(self._timestamps) - 1
            self._timestamps[self._live_index] = timestamp
            self._heights[self._live_index] = volume
            self._brushes[self._live_index] = brush
            self._update_lod_tail((timestamp, volume, is_bullish), append=False)
        else:
            self._timestamps.append(timestamp)
            self._heights.append(volume)
            self._brushes.append(brush)
            self._live_index = len(self._timestamps) - 1
            self._update_lod_tail((timestamp, volume, is_bullish), append=True)
        self._data_revision += 1
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

        view_box = self.graphics_item.getViewBox()
        viewport_width = (
            view_box.sceneBoundingRect().width() if view_box is not None else 0.0
        )
        level = 0
        if self._lod_enabled:
            level = select_lod_level(
                hi - lo,
                viewport_width,
                available_levels=len(self._lod_levels),
            )
        lod_lo, lod_hi = lod_slice_indices(lo, hi, level)
        rows = self._lod_levels[level][lod_lo:lod_hi]
        bucket_size = 1 << level
        render_width = self._bar_width * bucket_size
        signature = (
            lod_lo,
            lod_hi,
            self._data_revision,
            render_width,
            level,
        )
        if signature == self._last_applied_signature:
            return

        self.graphics_item.setOpts(
            x=[row[0] for row in rows],
            height=[row[1] for row in rows],
            width=render_width,
            brushes=[self._bull_brush if row[2] else self._bear_brush for row in rows],
        )
        self._last_applied_signature = signature
        self.applied_update_count += 1
        self.last_applied_lod_level = level
        self.last_applied_bar_count = len(rows)

    def _update_lod_tail(
        self,
        row: tuple[float, float, bool],
        *,
        append: bool,
    ) -> None:
        if not self._lod_levels:
            self._lod_levels = [[]]
        base = self._lod_levels[0]
        if append:
            base.append(row)
        elif base:
            base[-1] = row
        else:
            base.append(row)

        for level_index in range(1, len(self._lod_levels)):
            source = self._lod_levels[level_index - 1]
            target = self._lod_levels[level_index]
            source_start = ((len(source) - 1) // 2) * 2
            target_index = source_start // 2
            aggregate = aggregate_volume_bucket(source[source_start : source_start + 2])
            if target_index < len(target):
                target[target_index] = aggregate
                del target[target_index + 1 :]
            else:
                target.append(aggregate)

        while len(self._lod_levels[-1]) > 1:
            source = self._lod_levels[-1]
            self._lod_levels.append(
                [
                    aggregate_volume_bucket(source[index : index + 2])
                    for index in range(0, len(source), 2)
                ]
            )
