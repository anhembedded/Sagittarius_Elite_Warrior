"""`EPIC-029F` — the bot store, publishing `BotChangedEvent` after each write.

A decorator over `IBotStore` rather than a publish call in each writer: every
use case and every executor saves through the store, so this is the one place
that sees all of them (`fix-bug-rule.md` §1, move shared logic to the layer
that serves every consumer).

**A write that fails is still the bot's newest state** (`EPIC-035G`, D6). The file
keeps the last good record, so a reader would list a bot as RUNNING after it paused
for `STORAGE_FAILURE`, the one time the user most needs the truth. The decorator
keeps the record whose write failed (an `OSError`) in front of the file: `load` and
`load_all` return it, the failure is announced like any change so the screens read
again, and the next write that lands, or a delete, drops it. The error still
reaches the writer, which counts it (`BotRunState`). After a restart the file is
all there is, and reconciliation by tag and history re-derives the rest.
"""

from __future__ import annotations

import threading

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
        self._unsaved: dict[str, StoredBot] = {}
        self._lock = threading.Lock()

    def save(self, stored: StoredBot) -> None:
        bot_id = stored.bot.bot_id.value
        try:
            self._inner.save(stored)
        except OSError:
            with self._lock:
                self._unsaved[bot_id] = stored
            self._publisher.publish(BotChangedEvent(bot_id=bot_id))
            raise
        with self._lock:
            self._unsaved.pop(bot_id, None)
        self._publisher.publish(BotChangedEvent(bot_id=bot_id))

    def load(self, bot_id: BotId) -> StoredBot:
        with self._lock:
            unsaved = self._unsaved.get(bot_id.value)
        return unsaved if unsaved is not None else self._inner.load(bot_id)

    def load_all(self) -> BotStoreReading:
        reading = self._inner.load_all()
        with self._lock:
            unsaved = dict(self._unsaved)
        if not unsaved:
            return reading
        return BotStoreReading(
            tuple(
                unsaved.get(stored.bot.bot_id.value, stored) for stored in reading.bots
            ),
            reading.refused,
        )

    def delete(self, bot_id: BotId) -> None:
        self._inner.delete(bot_id)
        with self._lock:
            self._unsaved.pop(bot_id.value, None)
        self._publisher.publish(BotChangedEvent(bot_id=bot_id.value, removed=True))

    def exists(self, bot_id: BotId) -> bool:
        return self._inner.exists(bot_id)
