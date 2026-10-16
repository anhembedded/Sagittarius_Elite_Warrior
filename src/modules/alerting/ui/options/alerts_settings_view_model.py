"""State of the Alerts page of Tools → Options (`EPIC-036D1`).

@details The page holds no webhook. The line edit's text goes from the view to the
presenter in `save_requested` and nowhere in between; what the view model keeps is
words (the channel line, the saved line) and two booleans. A saved URL is never
read back into it: the saved line carries the last characters of the token, which
`DiscordChannelState.hint` already cut.
"""

from __future__ import annotations

from PySide6.QtCore import Signal, Slot
from Sagittarius_Elite_Warrior.src.support.ui_kit.status_view_model import (
    StatusMessageViewModel,
)


class AlertsSettingsViewModel(StatusMessageViewModel):
    """@brief State for the Alerts settings section."""

    channel_changed = Signal()
    working_changed = Signal()
    #: The webhook was kept: the view clears its field.
    webhook_kept = Signal()

    save_requested = Signal(str)
    remove_requested = Signal()
    send_test_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._channel_line = ""
        self._saved_line = ""
        self._can_remove = False
        self._can_test = False
        self._working_text = ""

    @property
    def channel_text(self) -> str:
        """Whether the Discord channel is on, off or waiting for a restart."""
        return self._channel_line

    @property
    def saved_text(self) -> str:
        """What is saved: the last characters of the token, or that nothing is."""
        return self._saved_line

    @property
    def can_remove_webhook(self) -> bool:
        return self._can_remove

    @property
    def can_send_test(self) -> bool:
        return self._can_test

    @property
    def working_text(self) -> str:
        """What is being done, or "" when nothing is."""
        return self._working_text

    @property
    def is_working(self) -> bool:
        return bool(self._working_text)

    def set_channel(
        self, channel_line: str, saved_line: str, *, can_remove: bool, can_test: bool
    ) -> None:
        self._channel_line = channel_line
        self._saved_line = saved_line
        self._can_remove = can_remove
        self._can_test = can_test
        self.channel_changed.emit()

    @Slot(str)
    def set_working(self, text: str) -> None:
        self._working_text = text
        self.working_changed.emit()

    def keep_webhook(self) -> None:
        self.webhook_kept.emit()

    @Slot(str)
    def request_save(self, value: str) -> None:
        self.save_requested.emit(value)

    @Slot()
    def request_remove(self) -> None:
        self.remove_requested.emit()

    @Slot()
    def request_send_test(self) -> None:
        self.send_test_requested.emit()
