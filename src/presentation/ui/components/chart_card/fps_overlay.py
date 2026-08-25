from PySide6.QtCore import QElapsedTimer, QEvent, QObject, Qt, QTimer
from PySide6.QtWidgets import QLabel, QWidget

_FPS_SAMPLE_INTERVAL_MS = 500
_OVERLAY_MARGIN = 8


class FrameRateSampler:
    """Counts completed chart paint events over a measured wall-clock sample."""

    def __init__(self) -> None:
        self._frame_count = 0

    def record_frame(self) -> None:
        self._frame_count += 1

    def reset(self) -> None:
        self._frame_count = 0

    def sample(self, elapsed_ms: int) -> float:
        frame_count = self._frame_count
        self.reset()
        if elapsed_ms <= 0:
            return 0.0
        return frame_count * 1000.0 / elapsed_ms


class ChartFpsOverlay(QObject):
    """Dev-only FPS label driven by actual paint events from the chart viewport."""

    def __init__(self, canvas: QWidget, parent: QObject | None = None) -> None:
        super().__init__(parent or canvas)
        self._canvas = canvas
        self._viewport = canvas.viewport()
        self._paint_sources: list[QWidget] = [self._viewport]
        self._sampler = FrameRateSampler()
        self._clock = QElapsedTimer()
        self._is_enabled = False

        self.label = QLabel("FPS 0.0", self._viewport)
        self.label.setObjectName("chartFpsOverlay")
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.label.setStyleSheet(
            "QLabel {"
            " color: #F0B90B;"  # token-exempt: chart_card avoids Palette, see theme.py
            " background: rgba(11, 14, 17, 190);"
            " border: 1px solid #474D57;"  # token-exempt: chart_card avoids Palette, see theme.py
            " border-radius: 3px;"
            " padding: 3px 6px;"
            " font-family: monospace;"
            " font-weight: 700;"
            "}"
        )
        self.label.adjustSize()
        self.label.hide()

        self._timer = QTimer(self)
        self._timer.setInterval(_FPS_SAMPLE_INTERVAL_MS)
        self._timer.timeout.connect(self._publish_sample)
        self._viewport.installEventFilter(self)
        self._position_label()

    def add_paint_source(self, source: QWidget) -> None:
        """Include a sibling preview surface in the measured chart FPS."""
        if source in self._paint_sources:
            return
        self._paint_sources.append(source)
        source.installEventFilter(self)

    def remove_paint_source(self, source: QWidget) -> None:
        if source not in self._paint_sources or source is self._viewport:
            return
        source.removeEventFilter(self)
        self._paint_sources.remove(source)

    @property
    def is_enabled(self) -> bool:
        return self._is_enabled

    @property
    def fps(self) -> float:
        value = self.label.text().removeprefix("FPS ")
        return float(value)

    def set_enabled(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if self._is_enabled == enabled:
            return
        self._is_enabled = enabled
        self._sampler.reset()
        if enabled:
            self.label.setText("FPS 0.0")
            self.label.adjustSize()
            self._position_label()
            self.label.show()
            self.label.raise_()
            self._clock.restart()
            self._timer.start()
            return
        self._timer.stop()
        self.label.hide()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched in self._paint_sources and event.type() == QEvent.Type.Paint:
            if self._is_enabled:
                self._sampler.record_frame()
                self.label.raise_()
        elif watched is self._viewport and event.type() == QEvent.Type.Resize:
            self._position_label()
        return super().eventFilter(watched, event)

    def _publish_sample(self) -> None:
        if not self._is_enabled:
            return
        elapsed_ms = self._clock.restart()
        fps = self._sampler.sample(elapsed_ms)
        self.label.setText(f"FPS {fps:.1f}")
        self.label.adjustSize()
        self._position_label()
        self.label.raise_()

    def _position_label(self) -> None:
        x = max(
            _OVERLAY_MARGIN,
            self._viewport.width() - self.label.width() - _OVERLAY_MARGIN,
        )
        self.label.move(x, _OVERLAY_MARGIN)

    def dispose(self) -> None:
        self._timer.stop()
        for source in self._paint_sources:
            source.removeEventFilter(self)
        self._paint_sources.clear()
        self.label.hide()
        self.label.deleteLater()
