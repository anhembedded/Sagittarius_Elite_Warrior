"""State of the Telegram part of the Alerts page of Tools → Options (`EPIC-036D4`).

@details Like the Discord part, it holds no secret. The two fields' text goes from the view to
the presenter in `save_requested` and nowhere in between; what this keeps is words (the channel
line, the saved line) and a boolean. A saved token is never read back into it: the saved line
carries the last characters of the token and the chat id, which `TelegramChannelState` already
cut.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot


class TelegramSettingsViewModel(QObject):
    channel_changed = Signal()
    #: The pair was kept: the view clears its fields.
    credentials_kept = Signal()

    save_requested = Signal(str, str)
    remove_requested = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._channel_line = ""
        self._saved_line = ""
        self._can_remove = False

    @property
    def channel_text(self) -> str:
        """Whether the Telegram channel is on, off or waiting for a restart."""
        return self._channel_line

    @property
    def saved_text(self) -> str:
        """What is saved: the last characters of the token and the chat, or that nothing is."""
        return self._saved_line

    @property
    def can_remove(self) -> bool:
        return self._can_remove

    def set_channel(
        self, channel_line: str, saved_line: str, *, can_remove: bool
    ) -> None:
        self._channel_line = channel_line
        self._saved_line = saved_line
        self._can_remove = can_remove
        self.channel_changed.emit()

    def keep_credentials(self) -> None:
        self.credentials_kept.emit()

    @Slot(str, str)
    def request_save(self, token: str, chat: str) -> None:
        self.save_requested.emit(token, chat)

    @Slot()
    def request_remove(self) -> None:
        self.remove_requested.emit()
