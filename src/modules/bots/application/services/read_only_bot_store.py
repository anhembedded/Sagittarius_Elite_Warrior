"""`EPIC-035H` — the bot store of a copy of the app that is read-only.

Every writer saves through `IBotStore` (the use cases, the executors, the
restart rule), so refusing the two writes here covers them all, and a second
copy of the app can never overwrite a running bot's file under the first. The
reads pass through, so the Bots tab still shows what is there.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.errors import ReadOnlyInstanceError
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import (
    BotStoreReading,
    IBotStore,
    StoredBot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId


class ReadOnlyBotStore(IBotStore):
    """Reads through; saves and deletes nothing."""

    def __init__(self, inner: IBotStore, reason: str) -> None:
        self._inner = inner
        self._reason = reason

    def save(self, stored: StoredBot) -> None:
        raise ReadOnlyInstanceError(self._reason)

    def load(self, bot_id: BotId) -> StoredBot:
        return self._inner.load(bot_id)

    def load_all(self) -> BotStoreReading:
        return self._inner.load_all()

    def delete(self, bot_id: BotId) -> None:
        raise ReadOnlyInstanceError(self._reason)

    def exists(self, bot_id: BotId) -> bool:
        return self._inner.exists(bot_id)
