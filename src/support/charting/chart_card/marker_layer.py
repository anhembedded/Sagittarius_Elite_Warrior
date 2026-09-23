from __future__ import annotations

import math
from collections.abc import Sequence

import pyqtgraph as pg
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsSimpleTextItem,
)

from .marker_lod import (
    DisplayMarker,
    MarkerDensityMode,
    MarkerPoint,
    classify_marker_density,
    select_marker_display,
    visible_candle_count,
)
from .viewport_culled_layer import ViewportCulledLayer
from .viewport_windowing import visible_slice_indices

_MARKER_HALF_WIDTH_PIXELS = 5.0
_MARKER_HEIGHT_PIXELS = 8.0
_MARKER_VERTICAL_OFFSET_PIXELS = 2.0
_DEFAULT_BORDER_DARKEN_RATIO = 120
_VIEWPORT_PADDING_RATIO = 0.1
_FALLBACK_VIEWPORT_WIDTH_PIXELS = 1200.0
_BADGE_HORIZONTAL_OFFSET_PIXELS = 8.0
_BADGE_FONT_POINT_SIZE = 8
_PRICE_DOT_RADIUS_PIXELS = 2.0


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
        self._badge_item = QGraphicsSimpleTextItem(self)
        badge_font = QFont()
        badge_font.setPointSize(_BADGE_FONT_POINT_SIZE)
        self._badge_item.setFont(badge_font)
        self._badge_item.setVisible(False)
        # `PROP-003` §3.1 MEDIUM mode — a small dot at this item's own local
        # origin, i.e. the exact (time, execution price) point the triangle
        # itself is offset away from by `_MARKER_VERTICAL_OFFSET_PIXELS`.
        self._price_dot_item = QGraphicsEllipseItem(
            -_PRICE_DOT_RADIUS_PIXELS,
            -_PRICE_DOT_RADIUS_PIXELS,
            _PRICE_DOT_RADIUS_PIXELS * 2,
            _PRICE_DOT_RADIUS_PIXELS * 2,
            self,
        )
        self._price_dot_item.setPen(QPen(Qt.PenStyle.NoPen))
        self._price_dot_item.setVisible(False)

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
        badge_text: str | None = None,
        show_price_dot: bool = False,
    ) -> None:
        if self._direction != direction:
            self._direction = direction
            self._update_geometry(direction)

        if self._color != color:
            self._color = color
            self.setBrush(brush)
            self.setPen(pen)
            self._badge_item.setBrush(brush)
            self._price_dot_item.setBrush(brush)

        self.setPos(x, y)
        if text:
            self.setToolTip(f"{text} @ {y:,.2f}" if y else text)
        else:
            self.setToolTip(f"{y:,.2f}")

        self._configure_badge(badge_text, direction)
        self._price_dot_item.setVisible(show_price_dot)

    def _configure_badge(self, badge_text: str | None, direction: str) -> None:
        """`PROP-003` §3.1 DETAILED mode — a persistent label next to the
        triangle, so a zoomed-in user reads PnL/reason without hovering.
        Only `MarkerLayer` decides when a viewport is detailed enough to
        pass non-`None` text here; this item just draws or hides it."""
        if not badge_text:
            self._badge_item.setVisible(False)
            return
        self._badge_item.setText(badge_text)
        offset_y = (
            _MARKER_VERTICAL_OFFSET_PIXELS + _MARKER_HEIGHT_PIXELS
            if direction == "up"
            else -_MARKER_VERTICAL_OFFSET_PIXELS - _MARKER_HEIGHT_PIXELS
        )
        self._badge_item.setPos(_BADGE_HORIZONTAL_OFFSET_PIXELS, offset_y)
        self._badge_item.setVisible(True)

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


class MarkerLayer(ViewportCulledLayer):
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
        #: `PROP-003` — per-marker badge text (e.g. "+2.10%"), keyed by the
        #: exact `MarkerPoint` tuple it belongs to. A marker absent here (a
        #: script marker with no badge, or an entry marker) never shows one.
        self._badges: dict[str, dict[MarkerPoint, str]] = {}
        #: `None` until the first `set_bar_seconds()` call — `_density_mode()`
        #: reads this as "spacing unknown" and stays DENSE (no badges) rather
        #: than guessing a candle count.
        self._bar_seconds: float | None = None
        self._last_density_mode: dict[str, MarkerDensityMode] = {}

    def set_markers(
        self,
        key: str,
        markers: list[MarkerPoint],
        badges: Sequence[str | None] | None = None,
    ) -> None:
        """
        @brief Replaces every marker belonging to one script with the given set.
        @details The full semantic history is retained, but only the visible
        timestamp slice is materialized as QGraphics scene items. This keeps
        pan/zoom cost proportional to visible markers rather than the entire
        Backtest history.

        `badges`, when given, is positional with `markers` (`badges[i]` is
        `markers[i]`'s own badge text, or `None` for no badge) — optional so
        every existing caller (custom indicator scripts via
        `IndicatorManager.set_script_markers`) keeps working unchanged.
        """
        self.clear(key)
        pairs = sorted(
            zip(markers, badges or [None] * len(markers), strict=True),
            key=lambda pair: pair[0][0],
        )
        self._markers[key] = tuple(marker for marker, _ in pairs)
        self._timestamps[key] = tuple(marker[0] for marker, _ in pairs)
        self._badges[key] = {
            marker: badge for marker, badge in pairs if badge is not None
        }
        self._active_items[key] = {}
        self._materialize_visible_slice(key)

    def set_bar_seconds(self, bar_seconds: float) -> None:
        """`PROP-003` — the chart's own candle spacing, used to translate
        the visible timestamp range into a visible-candle count for
        `MarkerDensityMode`. Called by `IndicatorManager` whenever
        `ChartCard` recomputes it (on data load and on every pan/zoom, both
        cheap: `ChartCard._bar_seconds()` is O(1)), never by this layer
        itself — a layer has no candle data of its own to derive it from."""
        self._bar_seconds = bar_seconds

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
        density_mode = self._density_mode()
        if (
            self._display_markers.get(key) == display_markers
            and self._last_density_mode.get(key) is density_mode
        ):
            return

        badges = self._badges.get(key, {})
        # `PROP-003` §3.1 MEDIUM mode — every displayed item gets the dot,
        # aggregated or not: unlike the badge, a dot only marks "a fill
        # happened here", which stays true of an aggregate's own
        # representative point.
        show_price_dot = density_mode is MarkerDensityMode.MEDIUM
        active_items = self._active_items.setdefault(key, {})
        reusable_items = [active_items[index] for index in sorted(active_items)]
        next_items: dict[int, TriangleMarkerItem] = {}
        for display_index, display_marker in enumerate(display_markers):
            # A badge only ever shows for an exact (non-aggregated) marker —
            # an aggregate item already speaks for several trades, so a
            # single one's PnL badge would misrepresent the group.
            badge_text = (
                badges.get(display_marker.source)
                if density_mode is MarkerDensityMode.DETAILED
                and display_marker.represented_count == 1
                else None
            )
            if display_index < len(reusable_items):
                item = reusable_items[display_index]
                self._configure_item(
                    item, display_marker.source, badge_text, show_price_dot
                )
            else:
                item = self._create_item(
                    display_marker.source, badge_text, show_price_dot
                )
                self._plot.addItem(item)
            next_items[display_index] = item

        for item in reusable_items[len(display_markers) :]:
            self._plot.removeItem(item)

        self._active_items[key] = next_items
        self._active_slices[key] = target_slice
        self._display_markers[key] = display_markers
        self._last_density_mode[key] = density_mode
        self._items[key] = [next_items[index] for index in sorted(next_items)]

    def _density_mode(self) -> MarkerDensityMode:
        """`PROP-003` — `DENSE` (no badges) until both a viewport and a
        real `set_bar_seconds()` value are known, matching today's
        behaviour exactly for every caller that never calls it."""
        if self._visible_range is None or self._bar_seconds is None:
            return MarkerDensityMode.DENSE
        min_x, max_x = self._visible_range
        candles = visible_candle_count(min_x, max_x, self._bar_seconds)
        return classify_marker_density(candles)

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

    def _create_item(
        self,
        marker: MarkerPoint,
        badge_text: str | None = None,
        show_price_dot: bool = False,
    ) -> TriangleMarkerItem:
        item = TriangleMarkerItem()
        self._configure_item(item, marker, badge_text, show_price_dot)
        return item

    def _configure_item(
        self,
        item: TriangleMarkerItem,
        marker: MarkerPoint,
        badge_text: str | None = None,
        show_price_dot: bool = False,
    ) -> None:
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
            badge_text=badge_text,
            show_price_dot=show_price_dot,
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
        self._badges.pop(key, None)
        self._last_density_mode.pop(key, None)

    def clear_all(self) -> None:
        for key in list(self._markers):
            self.clear(key)
