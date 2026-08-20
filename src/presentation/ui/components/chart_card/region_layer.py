from __future__ import annotations

import pyqtgraph as pg
from PySide6 import QtGui

from .viewport_culled_layer import ViewportCulledLayer
from .viewport_windowing import visible_span_indices

#: Drawn beneath candles/curves/volume so a background tint never occludes them.
_REGION_Z_VALUE = -10
_VIEWPORT_PADDING_RATIO = 0.1

#: (start_x, end_x, color, opacity)
RegionSpan = tuple[float, float, str, float]


def _color_with_alpha(color: str, opacity: float) -> QtGui.QColor:
    """@brief Turns a plain hex color + a 0..1 opacity into a QColor with alpha."""
    qcolor = pg.mkColor(color)
    qcolor.setAlphaF(max(0.0, min(1.0, opacity)))
    return qcolor


class RegionLayer(ViewportCulledLayer):
    """
    @brief Draws a script/strategy's background tint spans (BOT-032's
    `bgcolor()`-style regions, e.g. `BOT-113`'s trend-zone shading) as
    `pg.LinearRegionItem`s on the main price plot.

    @details BUG-024: this used to be 2 standalone methods on
    `IndicatorManager` that allocated one permanent `LinearRegionItem` per
    span with no viewport awareness at all — a 2,065-span backtest made
    every pan/zoom step ~9x slower. This mirrors `MarkerLayer`'s already-
    proven pattern instead: the full span history is retained, but only the
    spans overlapping the current viewport (+ a small edge margin) are ever
    materialized as scene items, via `visible_span_indices()`
    (`viewport_windowing.py`) — same O(log N) windowing every other
    renderer in this package uses.
    """

    def __init__(self, plot: pg.PlotItem) -> None:
        self._plot = plot
        self._spans: dict[str, tuple[RegionSpan, ...]] = {}
        self._active_slices: dict[str, tuple[int, int]] = {}
        self._items: dict[str, list[pg.LinearRegionItem]] = {}
        self._visible_range: tuple[float, float] | None = None

    def set_regions(self, key: str, spans: list[RegionSpan]) -> None:
        """
        @brief Replaces one script's background tint spans with the given
        set — always the full current series, same "always the whole
        series" contract as `IndicatorManager.update_data()`.
        """
        self._spans[key] = tuple(spans)
        self._active_slices.pop(key, None)
        self._materialize_visible_slice(key)

    def refresh_window(self, min_x: float, max_x: float) -> None:
        """Updates active scene items for the latest pan/zoom viewport."""
        self._visible_range = (min(min_x, max_x), max(min_x, max_x))
        for key in self._spans:
            self._materialize_visible_slice(key)

    def stored_span_count(self, key: str) -> int:
        return len(self._spans.get(key, ()))

    def active_span_count(self, key: str) -> int:
        return len(self._items.get(key, []))

    def _materialize_visible_slice(self, key: str) -> None:
        spans = self._spans.get(key, ())
        lo, hi = self._visible_slice(spans)
        target_slice = (lo, hi)
        if self._active_slices.get(key) == target_slice:
            return

        visible = spans[lo:hi]
        items = self._items.setdefault(key, [])
        for index, (start, end, color, opacity) in enumerate(visible):
            if index < len(items):
                item = items[index]
                if item.getRegion() != (start, end):
                    item.setRegion((start, end))
                item.setBrush(pg.mkBrush(_color_with_alpha(color, opacity)))
            else:
                item = self._create_item(start, end, color, opacity)
                self._plot.addItem(item)
                items.append(item)

        for item in items[len(visible) :]:
            self._plot.removeItem(item)
        del items[len(visible) :]

        self._active_slices[key] = target_slice

    def _visible_slice(self, spans: tuple[RegionSpan, ...]) -> tuple[int, int]:
        if self._visible_range is None:
            return 0, len(spans)
        min_x, max_x = self._visible_range
        padding = (max_x - min_x) * _VIEWPORT_PADDING_RATIO
        return visible_span_indices(spans, min_x, max_x, padding=padding)

    def _create_item(
        self, start: float, end: float, color: str, opacity: float
    ) -> pg.LinearRegionItem:
        item = pg.LinearRegionItem(
            values=(start, end),
            brush=pg.mkBrush(_color_with_alpha(color, opacity)),
            pen=pg.mkPen(None),
            movable=False,
        )
        item.setZValue(_REGION_Z_VALUE)
        return item

    def clear(self, key: str) -> None:
        """Removes every background span belonging to one script."""
        for item in self._items.pop(key, []):
            self._plot.removeItem(item)
        self._spans.pop(key, None)
        self._active_slices.pop(key, None)

    def clear_all(self) -> None:
        for key in list(self._spans):
            self.clear(key)
