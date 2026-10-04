"""A `QTimer` that fires `slot` once, `interval` ms after its last `start()`.

Restarting it before it fires pushes the shot back, so a burst of `start()`
calls is one call of `slot`: how a screen coalesces a burst of change events
into one read, or waits for typing to pause.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QTimer


def single_shot_timer(
    parent: QObject, interval: int, slot: Callable[[], None]
) -> QTimer:
    """@brief A stopped single-shot timer owned by `parent`, wired to `slot`."""
    timer = QTimer(parent)
    timer.setSingleShot(True)
    timer.setInterval(interval)
    timer.timeout.connect(slot)
    return timer
