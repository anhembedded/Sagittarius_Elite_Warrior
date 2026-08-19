from collections.abc import Callable

from PySide6.QtCore import QObject, QTimer

_UI_FRAME_INTERVAL_MS = 16


class RangeUpdateScheduler(QObject):
    """Coalesces X-range signal bursts and applies the final range per UI frame."""

    def __init__(
        self,
        apply_range: Callable[[float, float], None],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._apply_range = apply_range
        self._pending_range: tuple[float, float] | None = None
        self._disposed = False
        self.applied_count = 0
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(_UI_FRAME_INTERVAL_MS)
        self._timer.timeout.connect(self.flush_pending)

    @property
    def has_pending(self) -> bool:
        """Whether a coalesced range is still waiting to be applied.

        Read by diagnostics: a frame captured while this is True shows
        candles at the new range but indicators/volume at the old one.
        """
        return self._pending_range is not None

    def schedule(self, min_x: float, max_x: float) -> None:
        if self._disposed:
            return
        self._pending_range = (min(min_x, max_x), max(min_x, max_x))
        if not self._timer.isActive():
            self._timer.start()

    def flush_pending(self) -> None:
        if self._disposed or self._pending_range is None:
            return
        self._timer.stop()
        pending_range = self._pending_range
        self._pending_range = None
        self.applied_count += 1
        self._apply_range(*pending_range)

    def dispose(self) -> None:
        self._disposed = True
        self._pending_range = None
        self._timer.stop()
