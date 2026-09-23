"""`UiToastNotificationChannel` — `BOT-018`'s GUI channel.

@details
`ui-presentation-rule.md` §1 forbids hand-drawn chrome: `QMainWindow.
statusBar()` is the standard part for exactly this ("temporary status/
notification text"), so this channel needs no new widget — every screen
already sits inside one `MainWindow`, so a message shows regardless of
which screen the user is on.
"""

from __future__ import annotations

from PySide6.QtWidgets import QMainWindow
from Sagittarius_Elite_Warrior.src.core.contracts.i_notification_channel import (
    INotificationChannel,
)

#: Long enough to read a full sentence; short enough that a second
#: notification does not sit stale for a very long time before rotating.
_MESSAGE_TIMEOUT_MS = 10_000


class UiToastNotificationChannel(INotificationChannel):
    """Shows `message` in `window`'s status bar for a few seconds."""

    def __init__(self, window: QMainWindow) -> None:
        self._window = window

    def send(self, message: str) -> None:
        self._window.statusBar().showMessage(message, _MESSAGE_TIMEOUT_MS)
