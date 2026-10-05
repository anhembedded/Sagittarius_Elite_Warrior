"""A chart's paint rate, shown in developer sessions only.

@par A header label since `EPIC-033G`
It was a style-sheeted `QLabel` moved over the plot's top-right corner, an
overlay `ui-presentation-rule.md` §3 forbids. Now the label is a plain one the
card places in its header row, and this class only measures and writes it.
"""

from PySide6.QtCore import QElapsedTimer, QEvent, QObject, QTimer
from PySide6.QtWidgets import QLabel, QWidget

_FPS_SAMPLE_INTERVAL_MS = 500


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


class ChartFpsMeter(QObject):
    """Counts the chart viewport's paint events and shows the rate in `label`.

    The label has no parent until its owner places it (`ChartCard` puts it in
    its header); it is hidden until `set_enabled(True)`.
    """

    def __init__(self, viewport: QWidget, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._viewport = viewport
        self._paint_sources: list[QWidget] = [viewport]
        self._sampler = FrameRateSampler()
        self._clock = QElapsedTimer()
        self._is_enabled = False

        self.label = QLabel("FPS 0.0")
        self.label.setObjectName("chartFpsMeter")
        self.label.hide()

        self._timer = QTimer(self)
        self._timer.setInterval(_FPS_SAMPLE_INTERVAL_MS)
        self._timer.timeout.connect(self._publish_sample)
        viewport.installEventFilter(self)

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

    def release_viewport(self) -> None:
        """Stops watching the viewport, before its owner destroys it."""
        self._viewport.removeEventFilter(self)
        self._paint_sources.remove(self._viewport)

    def watch_viewport(self, viewport: QWidget) -> None:
        """Measures `viewport` from now on — the one that replaced it."""
        self._viewport = viewport
        self._paint_sources.insert(0, viewport)
        viewport.installEventFilter(self)

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
            self.label.show()
            self._clock.restart()
            self._timer.start()
            return
        self._timer.stop()
        self.label.hide()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if (
            watched in self._paint_sources
            and event.type() == QEvent.Type.Paint
            and self._is_enabled
        ):
            self._sampler.record_frame()
        return super().eventFilter(watched, event)

    def _publish_sample(self) -> None:
        if not self._is_enabled:
            return
        elapsed_ms = self._clock.restart()
        fps = self._sampler.sample(elapsed_ms)
        self.label.setText(f"FPS {fps:.1f}")

    def dispose(self) -> None:
        self._timer.stop()
        for source in self._paint_sources:
            source.removeEventFilter(self)
        self._paint_sources.clear()
