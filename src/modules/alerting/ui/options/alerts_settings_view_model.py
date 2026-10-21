"""State of the Alerts page of Tools → Options (`EPIC-036D1`).

@details The page holds no webhook. The line edit's text goes from the view to the
presenter in `save_requested` and nowhere in between; what the view model keeps is
words (the channel line, the saved line) and two booleans. A saved URL is never
read back into it: the saved line carries the last characters of the token, which
`DiscordChannelState.hint` already cut.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Signal, Slot
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.options.quiet_hours_view_model import (
    QuietHoursViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.options.routing_matrix_view_model import (
    RoutingMatrixViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.options.telegram_settings_view_model import (
    TelegramSettingsViewModel,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.status_view_model import (
    StatusMessageViewModel,
)


@dataclass(frozen=True, slots=True)
class BotModeRow:
    """One bot on the page and what it may tell (`BOT-191`): `mode` is a `BotAlertMode` value."""

    bot_id: str
    name: str
    mode: str


class AlertsSettingsViewModel(StatusMessageViewModel):
    """@brief State for the Alerts settings section."""

    channel_changed = Signal()
    working_changed = Signal()
    #: The webhook was kept: the view clears its field.
    webhook_kept = Signal()

    #: The bots listed under "Bots" changed, or one's mode did.
    bots_changed = Signal()

    save_requested = Signal(str)
    bot_mode_requested = Signal(str, str)
    remove_requested = Signal()
    send_test_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        #: The Telegram part, a view model of its own (`EPIC-036D4`).
        self.telegram = TelegramSettingsViewModel(self)
        #: The Quiet hours part (`EPIC-036D6`).
        self.quiet = QuietHoursViewModel(self)
        #: The routing matrix part (`EPIC-036D7`).
        self.routing = RoutingMatrixViewModel(self)
        self._channel_line = ""
        self._saved_line = ""
        self._can_remove = False
        self._can_test = False
        self._working_text = ""
        self._bot_rows: tuple[BotModeRow, ...] = ()
        self._bots_note = ""
        self._bots_editable = True

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

    @property
    def bot_rows(self) -> tuple[BotModeRow, ...]:
        return self._bot_rows

    @property
    def bots_note(self) -> str:
        """Said under the list when it cannot be shown or is empty; "" otherwise."""
        return self._bots_note

    @property
    def bots_editable(self) -> bool:
        """Whether the choices can be changed here: not in a read-only copy."""
        return self._bots_editable

    def set_bot_rows(
        self, rows: tuple[BotModeRow, ...], note: str = "", *, editable: bool = True
    ) -> None:
        self._bot_rows = rows
        self._bots_note = note
        self._bots_editable = editable
        self.bots_changed.emit()

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

    @Slot(str, str)
    def request_bot_mode(self, bot_id: str, mode: str) -> None:
        self.bot_mode_requested.emit(bot_id, mode)
