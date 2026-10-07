"""`EPIC-034D` — the strip above a bot: who it is, where it trades and
whether that account could be read.

Two stock labels, so the answer to "why can I not
start?" is on screen before any click and is never colour alone: the status is
a word. Retrying is Bots → Retry venue account, a command like every other of the
mode (`ui-presentation-rule.md` §6: the mode holds no button of its own). It
reads the view model, as the Plan panel does, and decides nothing.
"""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_table_models import (
    state_text,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view_model import (
    BotsViewModel,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.plain_label import plain_label

_SEPARATOR = " · "


class IdentityStrip(QWidget):
    """@brief The selected bot's name, kind, venue, connection and state."""

    def __init__(self, model: BotsViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("stripBotIdentity")
        self._model = model
        self.who = plain_label()
        self.who.setObjectName("lblBotIdentity")
        self.connection = plain_label()
        self.connection.setObjectName("lblBotConnection")
        self.connection.setWordWrap(True)
        #: The selected bot's venue, for the window's status bar, which shows
        #: it in every mode while a bot is selected (`EPIC-034D`).
        self.status_label = plain_label()
        self.status_label.setObjectName("lblBotVenueStatus")
        row = QHBoxLayout(self)
        row.setContentsMargins(6, 2, 6, 2)
        row.addWidget(self.who)
        row.addWidget(self.connection, 1)
        model.selection_changed.connect(self._write_strip)
        model.facts_changed.connect(self._write_strip)
        model.connect_changed.connect(self._write_strip)
        self._write_strip()

    def _write_strip(self) -> None:
        bot = self._model.selected
        view = self._model.connect_view
        self.setVisible(bot is not None)
        self.status_label.setVisible(bot is not None)
        if bot is None:
            return
        self.status_label.setText(f"Bot venue: {view.venue}, {view.status.lower()}")
        saved = state_text(bot.state)
        self.who.setText(f"{bot.name} ({bot.kind}){_SEPARATOR}{saved}")
        self.connection.setText(f"{view.venue}: {view.status}{_SEPARATOR}{view.detail}")
