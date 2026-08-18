from __future__ import annotations

from collections.abc import Callable

import pyqtgraph as pg
from PySide6.QtCore import QEvent, QObject, QPointF, Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QPixmap,
    QWheelEvent,
)
from PySide6.QtWidgets import QGraphicsView, QWidget

_BACKGROUND_COLOR = QColor("#0b0e14")
_CROSSHAIR_COLOR = QColor("#8a8f98")
_CROSSHAIR_WIDTH = 1.0
_WHEEL_COMMIT_INTERVAL_MS = 80
_WHEEL_DELTA_UNIT = 120.0
_WHEEL_ZOOM_FACTOR = 1.2
_MIN_PREVIEW_SCALE = 0.2
_MAX_PREVIEW_SCALE = 5.0


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


class _CachedFrameOverlay(QWidget):
    """Paints a cheap transformed frame while the real chart remains unchanged."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._frame = QPixmap()
        self._pan_x = 0.0
        self._scale = 1.0
        self._anchor = QPointF()
        self._cursor = QPointF()
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.hide()

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
        painter = QPainter(self)
        painter.fillRect(self.rect(), _BACKGROUND_COLOR)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        painter.translate(self._anchor.x() + self._pan_x, self._anchor.y())
        painter.scale(self._scale, self._scale)
        painter.translate(-self._anchor.x(), -self._anchor.y())
        painter.drawPixmap(0, 0, self._frame)
        painter.resetTransform()
        painter.setPen(QPen(_CROSSHAIR_COLOR, _CROSSHAIR_WIDTH, Qt.PenStyle.DashLine))
        painter.drawLine(
            QPointF(self._cursor.x(), 0.0),
            QPointF(self._cursor.x(), self.height()),
        )
        painter.drawLine(
            QPointF(0.0, self._cursor.y()),
            QPointF(self.width(), self._cursor.y()),
        )
        painter.end()


class CachedFrameInteractionController(QObject):
    """Previews pan/zoom as a pixmap transform, then commits exact chart data."""

    def __init__(
        self,
        *,
        canvas: QGraphicsView,
        main_plot: pg.PlotItem,
        on_preview_started: Callable[[], None],
        on_preview_finished: Callable[[QPointF], None],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._canvas = canvas
        self._main_plot = main_plot
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

    @property
    def is_preview_active(self) -> bool:
        return self._mode is not None

    @property
    def preview_surface(self) -> QWidget:
        return self._overlay

    def begin_pan(self, viewport_position: QPointF) -> bool:
        if not self._position_is_in_main_plot(viewport_position):
            return False
        self._begin_preview("pan", viewport_position)
        return True

    def update_pan(self, viewport_position: QPointF) -> None:
        if self._mode != "pan":
            return
        self._last_position = viewport_position
        self._overlay.set_pan(
            viewport_position.x() - self._start_position.x(),
            viewport_position,
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
        self._on_preview_started()
        self._overlay.begin(self._viewport.grab(), viewport_position)

    def _finish_preview(self, final_range: tuple[float, float]) -> None:
        final_cursor = self._last_position
        self._wheel_timer.stop()
        self._overlay.hide()
        self._mode = None
        self._main_plot.setXRange(*final_range, padding=0)
        self._on_preview_finished(final_cursor)

    def _position_is_in_main_plot(self, viewport_position: QPointF) -> bool:
        scene_position = self._canvas.mapToScene(viewport_position.toPoint())
        return self._main_plot.vb.sceneBoundingRect().contains(scene_position)

    def dispose(self) -> None:
        self._wheel_timer.stop()
        self._viewport.removeEventFilter(self)
        self._overlay.hide()
        self._overlay.deleteLater()
        self._mode = None
