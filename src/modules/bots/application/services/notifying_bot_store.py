"""`EPIC-029F` — the bot store, publishing `BotChangedEvent` after each write.

A decorator over `IBotStore` rather than a publish call in each writer: every
use case and every executor saves through the store, so this is the one place
that sees all of them (`fix-bug-rule.md` §1, move shared logic to the layer
that serves every consumer).
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_event_publisher import (
    IEventPublisher,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_changed_event import (
    BotChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import (
    BotStoreReading,
    IBotStore,
    StoredBot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId


class NotifyingBotStore(IBotStore):
    def __init__(self, inner: IBotStore, publisher: IEventPublisher) -> None:
        self._inner = inner
        self._publisher = publisher

    def save(self, stored: StoredBot) -> None:
        self._inner.save(stored)
        self._publisher.publish(BotChangedEvent(bot_id=stored.bot.bot_id.value))

    def load(self, bot_id: BotId) -> StoredBot:
        return self._inner.load(bot_id)

    def load_all(self) -> BotStoreReading:
        return self._inner.load_all()

    def delete(self, bot_id: BotId) -> None:
        self._inner.delete(bot_id)
        self._publisher.publish(BotChangedEvent(bot_id=bot_id.value, removed=True))

    def exists(self, bot_id: BotId) -> bool:
        return self._inner.exists(bot_id)
