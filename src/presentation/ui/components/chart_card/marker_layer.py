import math

import pyqtgraph as pg

from .marker_lod import DisplayMarker, MarkerPoint, select_marker_display
from .viewport_windowing import visible_slice_indices

_UP_ANCHOR = (0.5, 1.2)
_DOWN_ANCHOR = (0.5, -0.2)
_DEFAULT_MARKER_TEXT_COLOR = "#0B0E11"
_VIEWPORT_PADDING_RATIO = 0.1
_FALLBACK_VIEWPORT_WIDTH_PIXELS = 1200.0


class MarkerLayer:
    """
    @brief Draws labelled markers (Pine's `plotshape`) for custom indicator
    scripts — e.g. a "Buy"/"Sell" tag on a crossover bar.
    @details Always drawn on the main price plot, regardless of the owning
    script's `overlay` flag — the same reasoning IndicatorManager.
    set_script_regions uses for background tints: every `self.mark()` call
    seen in practice places a marker at a *price*-scale value (close, a
    price-scale indicator reading), so it is read against the visible price
    action, not against whichever subplot the script's own lines happen to
    live on.

    A shared registry.key namespace (not per-line) — one script's markers
    accumulate as one growing list across the whole run, same as
    IndicatorManager tracks one region-span timeline per script rather than
    per line.
    """

    def __init__(self, plot: pg.PlotItem) -> None:
        self._plot = plot
        self._markers: dict[str, tuple[MarkerPoint, ...]] = {}
        self._timestamps: dict[str, tuple[float, ...]] = {}
        self._active_items: dict[str, dict[int, pg.TextItem]] = {}
        self._active_slices: dict[str, tuple[int, int]] = {}
        self._display_markers: dict[str, tuple[DisplayMarker, ...]] = {}
        self._items: dict[str, list[pg.TextItem]] = {}
        self._brushes: dict[str, pg.QtGui.QBrush] = {}
        self._pens: dict[str, pg.QtGui.QPen] = {}
        self._visible_range: tuple[float, float] | None = None

    def set_markers(self, key: str, markers: list[MarkerPoint]) -> None:
        """
        @brief Replaces every marker belonging to one script with the given set.
        @details The full semantic history is retained, but only the visible
        timestamp slice is materialized as QGraphics scene items. This keeps
        pan/zoom cost proportional to visible markers rather than the entire
        Backtest history.
        """
        self.clear(key)
        ordered = tuple(sorted(markers, key=lambda marker: marker[0]))
        self._markers[key] = ordered
        self._timestamps[key] = tuple(marker[0] for marker in ordered)
        self._active_items[key] = {}
        self._materialize_visible_slice(key)

    def refresh_window(self, min_x: float, max_x: float) -> None:
        """Updates active scene items for the latest pan/zoom viewport."""
        self._visible_range = (min(min_x, max_x), max(min_x, max_x))
        for key in self._markers:
            self._materialize_visible_slice(key)

    def stored_marker_count(self, key: str) -> int:
        return len(self._markers.get(key, ()))

    def active_marker_count(self, key: str) -> int:
        return len(self._active_items.get(key, {}))

    def represented_marker_count(self, key: str) -> int:
        """Returns source events represented by the current exact/LOD items."""
        return sum(
            marker.represented_count for marker in self._display_markers.get(key, ())
        )

    def _materialize_visible_slice(self, key: str) -> None:
        markers = self._markers.get(key, ())
        lo, hi = self._visible_slice(key)
        target_slice = (lo, hi)
        display_markers = self._select_display_markers(markers[lo:hi])
        if self._display_markers.get(key) == display_markers:
            return

        active_items = self._active_items.setdefault(key, {})
        reusable_items = [active_items[index] for index in sorted(active_items)]
        next_items: dict[int, pg.TextItem] = {}
        for display_index, display_marker in enumerate(display_markers):
            if display_index < len(reusable_items):
                item = reusable_items[display_index]
                self._configure_item(item, display_marker.source)
            else:
                item = self._create_item(display_marker.source)
                self._plot.addItem(item)
            next_items[display_index] = item

        for item in reusable_items[len(display_markers) :]:
            self._plot.removeItem(item)

        self._active_items[key] = next_items
        self._active_slices[key] = target_slice
        self._display_markers[key] = display_markers
        self._items[key] = [next_items[index] for index in sorted(next_items)]

    def _select_display_markers(
        self, markers: tuple[MarkerPoint, ...]
    ) -> tuple[DisplayMarker, ...]:
        if not markers:
            return ()
        if self._visible_range is None:
            min_x, max_x = markers[0][0], markers[-1][0]
        else:
            min_x, max_x = self._visible_range
            padding = (max_x - min_x) * _VIEWPORT_PADDING_RATIO
            min_x -= padding
            max_x += padding
        return select_marker_display(
            markers,
            min_x=min_x,
            max_x=max_x,
            pixel_width=self._viewport_pixel_width(),
        )

    def _viewport_pixel_width(self) -> float:
        width = float(self._plot.getViewBox().sceneBoundingRect().width())
        if not math.isfinite(width) or width <= 0.0:
            return _FALLBACK_VIEWPORT_WIDTH_PIXELS
        return width

    def _visible_slice(self, key: str) -> tuple[int, int]:
        timestamps = self._timestamps.get(key, ())
        if self._visible_range is None:
            return 0, len(timestamps)
        min_x, max_x = self._visible_range
        padding = (max_x - min_x) * _VIEWPORT_PADDING_RATIO
        return visible_slice_indices(timestamps, min_x, max_x, padding=padding)

    def _create_item(self, marker: MarkerPoint) -> pg.TextItem:
        item = pg.TextItem(color=_DEFAULT_MARKER_TEXT_COLOR)
        self._configure_item(item, marker)
        return item

    def _configure_item(self, item: pg.TextItem, marker: MarkerPoint) -> None:
        x, y, text, color, direction = marker
        brush = self._brushes.get(color)
        if brush is None:
            brush = pg.mkBrush(color)
            self._brushes[color] = brush
        pen = self._pens.get(color)
        if pen is None:
            pen = pg.mkPen(color)
            self._pens[color] = pen
        item.setText(text, color=_DEFAULT_MARKER_TEXT_COLOR)
        item.setAnchor(_UP_ANCHOR if direction == "up" else _DOWN_ANCHOR)
        item.fill = brush
        item.border = pen
        item.setPos(x, y)
        item.update()

    def clear(self, key: str) -> None:
        """Removes every marker belonging to one script."""
        for item in self._active_items.pop(key, {}).values():
            self._plot.removeItem(item)
        self._markers.pop(key, None)
        self._timestamps.pop(key, None)
        self._active_slices.pop(key, None)
        self._display_markers.pop(key, None)
        self._items.pop(key, None)

    def clear_all(self) -> None:
        for key in list(self._markers):
            self.clear(key)
