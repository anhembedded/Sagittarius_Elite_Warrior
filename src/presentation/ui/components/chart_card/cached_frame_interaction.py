from __future__ import annotations

import logging
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import pyqtgraph as pg
from PySide6.QtCore import QEvent, QObject, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QPixmap,
    QRegion,
    QWheelEvent,
)
from PySide6.QtWidgets import QGraphicsView, QWidget

# Must live under "App": StdLogger attaches every handler to the "App" logger
# and sets `propagate = False` on it, so a `__name__`-based logger here has no
# handler anywhere in its chain and only Python's last-resort WARNING+ fallback
# would emit it — INFO diagnostics would vanish silently.
logger = logging.getLogger("App.CachedFrameInteraction")

_BACKGROUND_COLOR = QColor(
    "#0b0e14"  # token-exempt: chart_card avoids Palette, see theme.py
)
_CROSSHAIR_COLOR = QColor(
    "#8a8f98"  # token-exempt: chart_card avoids Palette, see theme.py
)
_CROSSHAIR_WIDTH = 1.0
_WHEEL_COMMIT_INTERVAL_MS = 80
_WHEEL_DELTA_UNIT = 120.0
_WHEEL_ZOOM_FACTOR = 1.2
_MIN_PREVIEW_SCALE = 0.2
_MAX_PREVIEW_SCALE = 5.0
#: How far a drag may travel before the real chart is re-rendered and the
#: cached frame re-grabbed. This is also the upper bound on the blank band a
#: pan can expose, since the frame holds no pixels beyond what it captured.
#:
#: Measured on a real 2276px-wide window with 5 000 candles: one re-anchor
#: costs ~30ms while drag events arrive every ~39ms and a cheap preview
#: repaint costs ~1.2ms, so re-anchoring every few events stays well inside
#: the frame budget. A percentage alone is not enough — 15% of a 2218px plot
#: is a 333px blank strip, plainly visible — so an absolute pixel cap bounds
#: it on wide monitors while the ratio keeps it proportionate on narrow ones.
_PAN_REANCHOR_VIEWPORT_RATIO = 0.05
_PAN_REANCHOR_MAX_PIXELS = 96.0


def shifted_x_range(
    initial_range: tuple[float, float],
    *,
    pixel_delta: float,
    viewport_width: float,
) -> tuple[float, float]:
    """Translate an X range opposite to the user's cached-frame drag."""
    if viewport_width <= 0.0:
        return initial_range
    minimum, maximum = initial_range
    data_delta = -(pixel_delta / viewport_width) * (maximum - minimum)
    return minimum + data_delta, maximum + data_delta


def zoomed_x_range(
    initial_range: tuple[float, float],
    *,
    anchor_ratio: float,
    preview_scale: float,
) -> tuple[float, float]:
    """Scale an X range while preserving the data point under the cursor."""
    minimum, maximum = initial_range
    clamped_anchor = max(0.0, min(1.0, anchor_ratio))
    safe_scale = max(_MIN_PREVIEW_SCALE, min(_MAX_PREVIEW_SCALE, preview_scale))
    initial_width = maximum - minimum
    anchor_value = minimum + initial_width * clamped_anchor
    final_width = initial_width / safe_scale
    final_minimum = anchor_value - final_width * clamped_anchor
    return final_minimum, final_minimum + final_width


@dataclass(frozen=True)
class _PaintStats:
    """Aggregated overlay repaint cost for one gesture."""

    count: int
    total_ms: float
    max_ms: float

    @property
    def average_ms(self) -> float:
        return self.total_ms / self.count if self.count else 0.0


@dataclass(frozen=True)
class _PannableRegion:
    """A rectangle of the cached frame that follows the user's pan/zoom.

    Everything not covered by one of these is chart chrome — the price axis
    and its tick labels, the header row — and stays pinned where it was
    grabbed. `follows_y` separates the plot data areas, which track the
    gesture on both axes, from the time-axis strip, which must track it
    horizontally only so its labels stay under their own candles without the
    text itself being stretched vertically by a zoom.
    """

    rect: QRectF
    follows_y: bool


class _CachedFrameOverlay(QWidget):
    """Paints a cheap transformed frame while the real chart remains unchanged."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._frame = QPixmap()
        self._pan_x = 0.0
        self._scale = 1.0
        self._anchor = QPointF()
        self._cursor = QPointF()
        self._regions: tuple[_PannableRegion, ...] = ()
        self._paint_count = 0
        self._paint_total_ms = 0.0
        self._paint_max_ms = 0.0
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.hide()

    def set_pannable_regions(self, regions: Sequence[_PannableRegion]) -> None:
        """Declares which parts of the cached frame follow the gesture."""
        self._regions = tuple(regions)

    @property
    def frame_size_text(self) -> str:
        return f"{self._frame.width()}x{self._frame.height()}@{self._frame.devicePixelRatio():g}x"

    @property
    def region_summary(self) -> str:
        return ", ".join(
            f"{'data' if region.follows_y else 'time-axis'}"
            f"({region.rect.x():.0f},{region.rect.y():.0f} "
            f"{region.rect.width():.0f}x{region.rect.height():.0f})"
            for region in self._regions
        )

    def drain_paint_stats(self) -> _PaintStats:
        """Returns repaint cost since the last drain, then resets it."""
        stats = _PaintStats(
            count=self._paint_count,
            total_ms=self._paint_total_ms,
            max_ms=self._paint_max_ms,
        )
        self._paint_count = 0
        self._paint_total_ms = 0.0
        self._paint_max_ms = 0.0
        return stats

    def begin(self, frame: QPixmap, cursor: QPointF) -> None:
        self._frame = frame
        self._pan_x = 0.0
        self._scale = 1.0
        self._anchor = cursor
        self._cursor = cursor
        self.show()
        self.raise_()
        self.update()

    def set_pan(self, pan_x: float, cursor: QPointF) -> None:
        self._pan_x = pan_x
        self._scale = 1.0
        self._cursor = cursor
        self.update()

    def set_zoom(self, scale: float, anchor: QPointF) -> None:
        self._pan_x = 0.0
        self._scale = scale
        self._anchor = anchor
        self._cursor = anchor
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        started_at = time.perf_counter()
        painter = QPainter(self)
        painter.fillRect(self.rect(), _BACKGROUND_COLOR)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        # Chrome first, untransformed: the axes, tick labels and headers stay
        # pinned exactly where they were grabbed. Applying the pan/zoom to the
        # whole frame instead is what made a drag look like the entire chart
        # widget sliding out of its own frame (BUG-009).
        painter.drawPixmap(0, 0, self._frame)
        for region in self._regions:
            self._paint_transformed_region(painter, region)
        self._paint_crosshair(painter)
        painter.end()
        elapsed_ms = (time.perf_counter() - started_at) * 1000.0
        self._paint_count += 1
        self._paint_total_ms += elapsed_ms
        self._paint_max_ms = max(self._paint_max_ms, elapsed_ms)

    def _paint_transformed_region(
        self, painter: QPainter, region: _PannableRegion
    ) -> None:
        """Redraws one region of the frame with the live pan/zoom applied."""
        painter.save()
        painter.setClipRect(region.rect)
        painter.fillRect(region.rect, _BACKGROUND_COLOR)
        anchor_y = self._anchor.y() if region.follows_y else 0.0
        painter.translate(self._anchor.x() + self._pan_x, anchor_y)
        painter.scale(self._scale, self._scale if region.follows_y else 1.0)
        painter.translate(-self._anchor.x(), -anchor_y)
        # Second clip, applied AFTER the transform so it is evaluated in the
        # frame's own coordinates: it restricts which *source* pixels may be
        # sampled to this same region. Without it a drag slides the cached
        # frame's axis strip in from the side and paints a second, ghost axis
        # on top of the candles.
        painter.setClipRect(region.rect, Qt.ClipOperation.IntersectClip)
        painter.drawPixmap(0, 0, self._frame)
        painter.restore()

    def _paint_crosshair(self, painter: QPainter) -> None:
        """Draws crosshair lines clipped to the plot areas.

        The real chart's crosshair is a pair of `pg.InfiniteLine` items living
        inside each ViewBox, so it never crosses the axis strip. Clipping here
        keeps the preview's crosshair consistent with it.
        """
        plot_areas = [region for region in self._regions if region.follows_y]
        if not plot_areas:
            return
        painter.save()
        clip_region = QRegion()
        for region in plot_areas:
            clip_region = clip_region.united(QRegion(region.rect.toRect()))
        painter.setClipRegion(clip_region)
        painter.setPen(QPen(_CROSSHAIR_COLOR, _CROSSHAIR_WIDTH, Qt.PenStyle.DashLine))
        painter.drawLine(
            QPointF(self._cursor.x(), 0.0),
            QPointF(self._cursor.x(), self.height()),
        )
        painter.drawLine(
            QPointF(0.0, self._cursor.y()),
            QPointF(self.width(), self._cursor.y()),
        )
        painter.restore()


class CachedFrameInteractionController(QObject):
    """Previews pan/zoom as a pixmap transform, then commits exact chart data."""

    def __init__(
        self,
        *,
        canvas: QGraphicsView,
        main_plot: pg.PlotItem,
        plots_provider: Callable[[], Sequence[pg.PlotItem]],
        on_before_frame_grab: Callable[[], None],
        on_preview_started: Callable[[], None],
        on_preview_finished: Callable[[QPointF], None],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._canvas = canvas
        self._main_plot = main_plot
        # Read lazily rather than snapshotted: subplots are added and removed
        # while the chart lives (indicator toggles), so a list captured at
        # construction time would go stale.
        self._plots_provider = plots_provider
        # Indicator/volume viewport windowing is applied on a coalescing
        # timer, so a frame grabbed immediately after an X-range change would
        # capture candles at the new range but indicators still at the old
        # one. Called before every grab to settle that first.
        self._on_before_frame_grab = on_before_frame_grab
        self._viewport = canvas.viewport()
        self._overlay = _CachedFrameOverlay(self._viewport)
        self._on_preview_started = on_preview_started
        self._on_preview_finished = on_preview_finished
        self._mode: str | None = None
        self._start_position = QPointF()
        self._last_position = QPointF()
        self._initial_range = (0.0, 0.0)
        self._view_width = 0.0
        self._anchor_ratio = 0.5
        self._preview_scale = 1.0
        self._wheel_timer = QTimer(self)
        self._wheel_timer.setSingleShot(True)
        self._wheel_timer.setInterval(_WHEEL_COMMIT_INTERVAL_MS)
        self._wheel_timer.timeout.connect(self.commit_zoom)
        self._viewport.installEventFilter(self)
        # BUG-009 diagnostics. Deliberately per-gesture, never per mouse-move:
        # a drag emits hundreds of moves, so anything logged per event would
        # be unreadable in exactly the report it exists to produce.
        self._gesture_index = 0
        self._gesture_started_at = 0.0
        self._gesture_updates = 0
        self._gesture_reanchors = 0
        self._gesture_max_exposed_ratio = 0.0

    @property
    def is_preview_active(self) -> bool:
        return self._mode is not None

    @property
    def preview_surface(self) -> QWidget:
        return self._overlay

    def begin_pan(self, viewport_position: QPointF) -> bool:
        if not self._position_is_in_main_plot(viewport_position):
            # The distinguishing case from the BUG-009 report: a press here
            # bypasses the preview entirely and pyqtgraph pans natively, which
            # is why dragging from the volume subplot never showed the defect.
            logger.info(
                "[cached-frame] press at (%.0f, %.0f) is outside the main "
                "plot — preview NOT used, native pyqtgraph pan handles it",
                viewport_position.x(),
                viewport_position.y(),
            )
            return False
        self._begin_preview("pan", viewport_position)
        return True

    def update_pan(self, viewport_position: QPointF) -> None:
        if self._mode != "pan":
            return
        self._last_position = viewport_position
        pan_x = viewport_position.x() - self._start_position.x()
        self._gesture_updates += 1
        if self._view_width > 0.0:
            self._gesture_max_exposed_ratio = max(
                self._gesture_max_exposed_ratio, abs(pan_x) / self._view_width
            )
        if self._pan_exceeds_cached_frame(pan_x):
            self._reanchor_pan(viewport_position)
            return
        self._overlay.set_pan(pan_x, viewport_position)

    def _pan_exceeds_cached_frame(self, pan_x: float) -> bool:
        """Reports whether the drag has outrun the pixels the frame holds."""
        if self._view_width <= 0.0:
            return False
        return abs(pan_x) >= self._reanchor_threshold_pixels

    @property
    def _reanchor_threshold_pixels(self) -> float:
        return min(
            self._view_width * _PAN_REANCHOR_VIEWPORT_RATIO,
            _PAN_REANCHOR_MAX_PIXELS,
        )

    def _reanchor_pan(self, viewport_position: QPointF) -> None:
        """Re-renders the real plot mid-drag and restarts the preview from it.

        A cached frame only holds the pixels that were on screen when the drag
        began, so translating it far enough exposes an ever-widening band the
        frame simply has no content for — the blank area users report. Paying
        for one real render once the drag passes
        `_PAN_REANCHOR_VIEWPORT_RATIO` of the viewport caps that band at that
        fraction instead of letting it grow without limit, while still
        serving every frame in between from the cheap pixmap transform.
        """
        started_at = time.perf_counter()
        pan_x = viewport_position.x() - self._start_position.x()
        final_range = shifted_x_range(
            self._initial_range,
            pixel_delta=pan_x,
            viewport_width=self._view_width,
        )
        self._main_plot.setXRange(*final_range, padding=0)
        self._initial_range = final_range
        self._start_position = viewport_position
        # Hidden before grabbing, or the stale overlay would be captured into
        # the very frame meant to replace it.
        self._overlay.hide()
        self._on_before_frame_grab()
        frame = self._viewport.grab()
        self._overlay.set_pannable_regions(self._pannable_regions())
        self._overlay.begin(frame, viewport_position)
        self._gesture_reanchors += 1
        logger.info(
            "[cached-frame] gesture #%d re-anchor %d: pan %+.0fpx (%.0f%% of "
            "%.0fpx plot) -> re-render+re-grab took %.1fms, new x-range "
            "[%.1f, %.1f], frame %s",
            self._gesture_index,
            self._gesture_reanchors,
            pan_x,
            abs(pan_x) / self._view_width * 100.0 if self._view_width else 0.0,
            self._view_width,
            (time.perf_counter() - started_at) * 1000.0,
            final_range[0],
            final_range[1],
            self._overlay.frame_size_text,
        )

    def commit_pan(self, viewport_position: QPointF | None = None) -> None:
        if self._mode != "pan":
            return
        if viewport_position is not None:
            self._last_position = viewport_position
        final_range = shifted_x_range(
            self._initial_range,
            pixel_delta=self._last_position.x() - self._start_position.x(),
            viewport_width=self._view_width,
        )
        self._finish_preview(final_range)

    def begin_zoom(self, viewport_position: QPointF) -> bool:
        if not self._position_is_in_main_plot(viewport_position):
            return False
        self._begin_preview("zoom", viewport_position)
        scene_position = self._canvas.mapToScene(viewport_position.toPoint())
        view_rect = self._main_plot.vb.sceneBoundingRect()
        self._anchor_ratio = (scene_position.x() - view_rect.left()) / view_rect.width()
        self._anchor_ratio = max(0.0, min(1.0, self._anchor_ratio))
        return True

    def update_zoom(self, *, preview_scale: float) -> None:
        if self._mode != "zoom":
            return
        self._preview_scale = max(
            _MIN_PREVIEW_SCALE,
            min(_MAX_PREVIEW_SCALE, preview_scale),
        )
        self._overlay.set_zoom(self._preview_scale, self._start_position)

    def commit_zoom(self) -> None:
        if self._mode != "zoom":
            return
        final_range = zoomed_x_range(
            self._initial_range,
            anchor_ratio=self._anchor_ratio,
            preview_scale=self._preview_scale,
        )
        self._finish_preview(final_range)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is not self._viewport:
            return False
        if event.type() == QEvent.Type.Resize:
            # A resize mid-preview (window resize, splitter move, dynamic
            # layout reflow) invalidates the cached pixmap `begin()` grabbed
            # at the old viewport size — it never gets re-grabbed, so
            # stretching it across a now-larger overlay would leave most of
            # the overlay painted with `_BACKGROUND_COLOR` around a small,
            # stale surviving patch (BUG-009). Commit immediately instead:
            # this hides the overlay and applies the exact in-progress
            # pan/zoom to the live plot, which then resizes correctly on its
            # own.
            if self.is_preview_active:
                if self._mode == "pan":
                    self.commit_pan()
                else:
                    self.commit_zoom()
            self._overlay.setGeometry(self._viewport.rect())
            return False
        if isinstance(event, QMouseEvent):
            return self._filter_mouse_event(event)
        if isinstance(event, QWheelEvent):
            return self._filter_wheel_event(event)
        return False

    def _filter_mouse_event(self, event: QMouseEvent) -> bool:
        if (
            event.type() == QEvent.Type.MouseButtonPress
            and event.button() == Qt.MouseButton.LeftButton
            and self._main_plot.vb.state["mouseMode"] == self._main_plot.vb.PanMode
        ):
            return self.begin_pan(event.position())
        if event.type() == QEvent.Type.MouseMove and self._mode == "pan":
            self.update_pan(event.position())
            return True
        if (
            event.type() == QEvent.Type.MouseButtonRelease
            and event.button() == Qt.MouseButton.LeftButton
            and self._mode == "pan"
        ):
            self.commit_pan(event.position())
            return True
        return False

    def _filter_wheel_event(self, event: QWheelEvent) -> bool:
        if self._mode == "pan":
            return False
        if self._mode != "zoom" and not self.begin_zoom(event.position()):
            return False
        wheel_steps = event.angleDelta().y() / _WHEEL_DELTA_UNIT
        self.update_zoom(
            preview_scale=self._preview_scale * (_WHEEL_ZOOM_FACTOR**wheel_steps)
        )
        self._wheel_timer.start()
        return True

    def _begin_preview(self, mode: str, viewport_position: QPointF) -> None:
        if self.is_preview_active:
            if self._mode == "pan":
                self.commit_pan()
            else:
                self.commit_zoom()
        self._mode = mode
        self._start_position = viewport_position
        self._last_position = viewport_position
        current_range = self._main_plot.vb.viewRange()[0]
        self._initial_range = (current_range[0], current_range[1])
        self._view_width = self._main_plot.vb.sceneBoundingRect().width()
        self._preview_scale = 1.0
        self._overlay.setGeometry(self._viewport.rect())
        self._overlay.set_pannable_regions(self._pannable_regions())
        self._on_preview_started()
        self._on_before_frame_grab()
        grab_started_at = time.perf_counter()
        self._overlay.begin(self._viewport.grab(), viewport_position)
        self._overlay.drain_paint_stats()
        self._gesture_index += 1
        self._gesture_started_at = time.perf_counter()
        self._gesture_updates = 0
        self._gesture_reanchors = 0
        self._gesture_max_exposed_ratio = 0.0
        logger.info(
            "[cached-frame] gesture #%d BEGIN %s at (%.0f, %.0f) | viewport "
            "%dx%d | overlay %dx%d | frame %s (grab %.1fms) | plot width "
            "%.0fpx | x-range [%.1f, %.1f] | reanchor threshold %.0fpx "
            "(%.0f%%) | regions: %s",
            self._gesture_index,
            mode,
            viewport_position.x(),
            viewport_position.y(),
            self._viewport.width(),
            self._viewport.height(),
            self._overlay.width(),
            self._overlay.height(),
            self._overlay.frame_size_text,
            (time.perf_counter() - grab_started_at) * 1000.0,
            self._view_width,
            self._initial_range[0],
            self._initial_range[1],
            self._reanchor_threshold_pixels,
            self._reanchor_threshold_pixels / self._view_width * 100.0
            if self._view_width
            else 0.0,
            self._overlay.region_summary,
        )

    def _pannable_regions(self) -> list[_PannableRegion]:
        """Maps the parts of the chart that follow the gesture into viewport
        coordinates.

        All plots are X-linked to the main plot, so a pan/zoom preview has to
        move the candles and the volume bars together; each keeps its own
        clip so neither one bleeds over the other's axis. The bottom-most
        plot's time axis is included horizontally so its labels stay under
        the candles they belong to for the whole gesture.
        """
        plots = list(self._plots_provider())
        regions: list[_PannableRegion] = []
        for plot in plots:
            regions.append(
                _PannableRegion(
                    rect=self._to_viewport_rect(plot.vb.sceneBoundingRect()),
                    follows_y=True,
                )
            )
        if plots:
            label_band = self._time_label_band(plots[-1])
            if not label_band.isEmpty():
                regions.append(_PannableRegion(rect=label_band, follows_y=False))
        return regions

    def _time_label_band(self, bottom_plot: pg.PlotItem) -> QRectF:
        """Isolates the time axis's tick-label strip below the bottom plot.

        A bottom `AxisItem`'s own bounding rect spans the plot area as well as
        its labels, so using it directly would repaint the bottom plot's data
        a second time with the horizontal-only transform and undo that plot's
        vertical zoom.
        """
        axis_rect = self._to_viewport_rect(
            bottom_plot.getAxis("bottom").sceneBoundingRect()
        )
        plot_rect = self._to_viewport_rect(bottom_plot.vb.sceneBoundingRect())
        return QRectF(
            axis_rect.x(),
            plot_rect.bottom(),
            axis_rect.width(),
            axis_rect.bottom() - plot_rect.bottom(),
        )

    def _to_viewport_rect(self, scene_rect: QRectF) -> QRectF:
        return QRectF(self._canvas.mapFromScene(scene_rect).boundingRect())

    def _finish_preview(self, final_range: tuple[float, float]) -> None:
        final_cursor = self._last_position
        mode = self._mode
        self._wheel_timer.stop()
        self._overlay.hide()
        self._mode = None
        self._main_plot.setXRange(*final_range, padding=0)
        self._on_preview_finished(final_cursor)
        paint_stats = self._overlay.drain_paint_stats()
        logger.info(
            "[cached-frame] gesture #%d END %s after %.0fms | %d updates, %d "
            "re-anchors | max exposed band %.0fpx (%.0f%% of plot)%s | overlay "
            "repaints %d (avg %.2fms, max %.2fms) | final x-range [%.1f, %.1f]",
            self._gesture_index,
            mode,
            (time.perf_counter() - self._gesture_started_at) * 1000.0,
            self._gesture_updates,
            self._gesture_reanchors,
            self._gesture_max_exposed_ratio * self._view_width,
            self._gesture_max_exposed_ratio * 100.0,
            # Overshooting by up to one drag step is normal: move events
            # arrive in jumps of tens of pixels, so the crossing is detected
            # slightly past the line. Only flag a real overshoot.
            ""
            if self._gesture_max_exposed_ratio * self._view_width
            <= self._reanchor_threshold_pixels * 2.0
            else " <-- FAR OVER THRESHOLD, re-anchor is not keeping up",
            paint_stats.count,
            paint_stats.average_ms,
            paint_stats.max_ms,
            final_range[0],
            final_range[1],
        )

    def _position_is_in_main_plot(self, viewport_position: QPointF) -> bool:
        scene_position = self._canvas.mapToScene(viewport_position.toPoint())
        return self._main_plot.vb.sceneBoundingRect().contains(scene_position)

    def dispose(self) -> None:
        self._wheel_timer.stop()
        self._viewport.removeEventFilter(self)
        self._overlay.hide()
        self._overlay.deleteLater()
        self._mode = None
