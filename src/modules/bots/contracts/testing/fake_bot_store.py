"""`EPIC-029B` — the verified in-memory `IBotStore` (HLD §10.3).

Passes `BotStoreContract`, the same suite `JsonBotStore` passes, so a use case
tested against it is tested against the real store's behaviour. It adds one
thing the port does not declare, `refuse_file()`, so a consumer can prove it
surfaces a refused file; `tests/unit/modules/bots/contracts/` verifies it.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import (
    BotNotFoundError,
    BotStoreReading,
    IBotStore,
    RefusedBotFile,
    StoredBot,
    UnreadableBotError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId


class FakeBotStore(IBotStore):
    """Bots in a dict, keyed by id."""

    def __init__(self) -> None:
        self._bots: dict[str, StoredBot] = {}
        self._refused: dict[str, RefusedBotFile] = {}

    def save(self, stored: StoredBot) -> None:
        self._bots[stored.bot.bot_id.value] = stored

    def load(self, bot_id: BotId) -> StoredBot:
        refused = self._refused.get(bot_id.value)
        if refused is not None:
            raise UnreadableBotError(refused.name, refused.reason)
        try:
            return self._bots[bot_id.value]
        except KeyError:
            raise BotNotFoundError(bot_id) from None

    def load_all(self) -> BotStoreReading:
        return BotStoreReading(
            tuple(self._bots[key] for key in sorted(self._bots)),
            tuple(self._refused[key] for key in sorted(self._refused)),
        )

    def delete(self, bot_id: BotId) -> None:
        if self._bots.pop(bot_id.value, None) is None:
            raise BotNotFoundError(bot_id)

    def exists(self, bot_id: BotId) -> bool:
        return bot_id.value in self._bots or bot_id.value in self._refused

    def refuse_file(self, bot_id: BotId, reason: str) -> None:
        """Make `bot_id` a file the store holds but cannot read."""
        self._bots.pop(bot_id.value, None)
        self._refused[bot_id.value] = RefusedBotFile(f"{bot_id.value}.json", reason)
