"""`UiToastNotificationChannel` — `BOT-018`'s GUI channel.

@details
`ui-presentation-rule.md` §1 forbids hand-drawn chrome: `QMainWindow.
statusBar()` is the standard part for exactly this ("temporary status/
notification text"), so this channel needs no new widget — every screen
already sits inside one `MainWindow`, so a message shows regardless of
which screen the user is on.

**A `QObject`, on purpose (`architecture-rule.md` §2.1 reason (a)).**
`NotificationEventHandler` dispatches every channel's `send()` off the main
thread via `ITaskManager` (never blocking whatever thread published the
triggering event), and one of the three events it fans out —
`TaskFailed` (`runtime.tasks.failed`) — is itself always published from a
background worker (`base_feed.py` names this exact event as the reason its
own bus wrapper exists). Touching `QMainWindow.statusBar()` from that
thread is the `BUG-031` bug class. `send()` therefore only ever emits a
Qt signal; the signal's default `AutoConnection` becomes a queued,
main-thread delivery whenever the emitting thread differs from this
object's own (main-thread) affinity, and `_display()` — the only method
that actually touches the widget — always runs there.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QMainWindow

#: Long enough to read a full sentence; short enough that a second
#: notification does not sit stale for a very long time before rotating.
_MESSAGE_TIMEOUT_MS = 10_000


class UiToastNotificationChannel(QObject):
    """Shows `message` in `window`'s status bar for a few seconds."""

    _message_ready = Signal(str)

    def __init__(self, window: QMainWindow) -> None:
        super().__init__(window)
        self._window = window
        self._message_ready.connect(self._display)

    def send(self, message: str) -> None:
        self._message_ready.emit(message)

    def _display(self, message: str) -> None:
        self._window.statusBar().showMessage(message, _MESSAGE_TIMEOUT_MS)
