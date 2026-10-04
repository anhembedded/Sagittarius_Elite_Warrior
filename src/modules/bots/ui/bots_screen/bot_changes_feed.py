"""`EPIC-029F` — the Bots screen's one listener to `BotChangedEvent`.

The store publishes after every write, from whichever thread wrote (a use
case on the screen's pool, a bot's own worker). `BaseFeed` brings it to the
Qt thread; the screen then reads the list again.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_changed_event import (
    BotChangedEvent,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.base_feed import BaseFeed


class BotChangesFeed(BaseFeed):
    """@brief Re-emits each bot write on the Qt thread."""

    #: The bot's id, and whether it was deleted.
    changed = Signal(str, bool)

    def _subscribe(self) -> None:
        self._events.on(BotChangedEvent, self._forward)

    def _forward(self, event: BotChangedEvent) -> None:
        self.changed.emit(event.bot_id, event.removed)
