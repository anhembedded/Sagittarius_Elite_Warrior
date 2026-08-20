from __future__ import annotations

import math

import pyqtgraph as pg
from PySide6.QtCore import QPointF
from PySide6.QtGui import QBrush, QColor, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QGraphicsItem, QGraphicsPathItem

from .marker_lod import DisplayMarker, MarkerPoint, select_marker_display
from .viewport_windowing import visible_slice_indices

_MARKER_HALF_WIDTH_PIXELS = 5.0
_MARKER_HEIGHT_PIXELS = 8.0
_MARKER_VERTICAL_OFFSET_PIXELS = 2.0
_DEFAULT_BORDER_DARKEN_RATIO = 120
_VIEWPORT_PADDING_RATIO = 0.1
_FALLBACK_VIEWPORT_WIDTH_PIXELS = 1200.0


class TriangleMarkerItem(QGraphicsPathItem):
    """
    @brief Compact, fixed-pixel triangle marker (TradingView style) for trade entries and exits.
    @details
    - Renders as a small solid triangle (width 10px, height 8px), matching native C++ chart dimensions.
    - 'up' (BUY / LONG ENTRY / SHORT COVER): Triangle points UP (▲), positioned below the candle price.
    - 'down' (SELL / LONG EXIT / SHORT ENTRY): Triangle points DOWN (▼), positioned above the candle price.
    - Uses `ItemIgnoresTransformations` so the marker maintains constant screen pixel size regardless of chart zoom/pan.
    - Tooltip displays full execution details on hover (e.g. 'MUA (LONG) @ 69,400.00') without cluttering the chart.
    """

    def __init__(self, parent: QGraphicsItem | None = None) -> None:
        super().__init__(parent)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self._direction: str = ""
        self._color: str = ""

    def configure(
        self,
        *,
        x: float,
        y: float,
        text: str,
        color: str,
        direction: str,
        brush: QBrush,
        pen: QPen,
    ) -> None:
        if self._direction != direction:
            self._direction = direction
            self._update_geometry(direction)

        if self._color != color:
            self._color = color
            self.setBrush(brush)
            self.setPen(pen)

        self.setPos(x, y)
        if text:
            self.setToolTip(f"{text} @ {y:,.2f}" if y else text)
        else:
            self.setToolTip(f"{y:,.2f}")

    def _update_geometry(self, direction: str) -> None:
        path = QPainterPath()
        half_w = _MARKER_HALF_WIDTH_PIXELS
        h = _MARKER_HEIGHT_PIXELS
        offset = _MARKER_VERTICAL_OFFSET_PIXELS

        if direction == "up":
            poly = QPolygonF(
                [
                    QPointF(0.0, offset),
                    QPointF(half_w, offset + h),
                    QPointF(-half_w, offset + h),
                ]
            )
        else:
            poly = QPolygonF(
                [
                    QPointF(0.0, -offset),
                    QPointF(half_w, -offset - h),
                    QPointF(-half_w, -offset - h),
                ]
            )
        path.addPolygon(poly)
        self.setPath(path)


class MarkerLayer:
    """
    @brief Draws compact triangle markers for trade entries, exits, and custom indicator scripts.
    @details Always drawn on the main price plot, regardless of the owning
    script's `overlay` flag.

    A shared registry.key namespace (not per-line) — one script's markers
    accumulate as one growing list across the whole run. Only the visible
    timestamp slice is materialized as scene items to keep pan/zoom cost
    proportional to visible markers rather than the entire history.
    """

    def __init__(self, plot: pg.PlotItem) -> None:
        self._plot = plot
        self._markers: dict[str, tuple[MarkerPoint, ...]] = {}
        self._timestamps: dict[str, tuple[float, ...]] = {}
        self._active_items: dict[str, dict[int, TriangleMarkerItem]] = {}
        self._active_slices: dict[str, tuple[int, int]] = {}
        self._display_markers: dict[str, tuple[DisplayMarker, ...]] = {}
        self._items: dict[str, list[TriangleMarkerItem]] = {}
        self._brushes: dict[str, QBrush] = {}
        self._pens: dict[str, QPen] = {}
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
        next_items: dict[int, TriangleMarkerItem] = {}
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

    def _create_item(self, marker: MarkerPoint) -> TriangleMarkerItem:
        item = TriangleMarkerItem()
        self._configure_item(item, marker)
        return item

    def _configure_item(self, item: TriangleMarkerItem, marker: MarkerPoint) -> None:
        x, y, text, color, direction = marker
        brush = self._brushes.get(color)
        if brush is None:
            brush = QBrush(QColor(color))
            self._brushes[color] = brush
        pen = self._pens.get(color)
        if pen is None:
            pen = QPen(QColor(color).darker(_DEFAULT_BORDER_DARKEN_RATIO), 1)
            self._pens[color] = pen
        item.configure(
            x=x,
            y=y,
            text=text,
            color=color,
            direction=direction,
            brush=brush,
            pen=pen,
        )

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
