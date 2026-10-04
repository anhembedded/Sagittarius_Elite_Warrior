"""`EPIC-029B` — a stored bot by id, or the refusal that explains why there is none.

Every command that names a bot starts here, so "no such bot" and "its file
cannot be read" are refused the same way everywhere (`BotCommandResult`).
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import (
    BotNotFoundError,
    IBotStore,
    StoredBot,
    UnreadableBotError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import (
    BotId,
    InvalidBotIdError,
)

logger = logging.getLogger("App.Bots.Lifecycle")


class BotLookup:
    """A stored bot, or the refusal that explains why there is none."""

    def __init__(self, store: IBotStore) -> None:
        self._store = store

    def find(self, bot_id: str) -> StoredBot | BotCommandResult:
        try:
            return self._store.load(BotId(bot_id))
        except (InvalidBotIdError, BotNotFoundError):
            return BotCommandResult.refused(
                BotRefusal.NOT_FOUND, f"No bot {bot_id!r}", bot_id
            )
        except UnreadableBotError as exc:
            return BotCommandResult.refused(BotRefusal.UNREADABLE, str(exc), bot_id)
