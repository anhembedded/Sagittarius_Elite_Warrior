"""`EPIC-029B` — handler for `GetBotQuery`.

`None` for an id no stored bot has, including one whose file is refused: the
list (`ListBotsQuery`) is where a refused file is named.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_bot.query import (
    GetBotQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_progress_reader import (
    bot_progress,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import (
    BotNotFoundError,
    IBotStore,
    UnreadableBotError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import (
    BotId,
    InvalidBotIdError,
)


class GetBotQueryHandler(IQueryHandler[GetBotQuery, BotSnapshot | None]):
    """One bot as a snapshot, or `None`."""

    def __init__(self, store: IBotStore) -> None:
        self._store = store

    def execute(self, query: GetBotQuery) -> BotSnapshot | None:
        try:
            stored = self._store.load(BotId(query.bot_id))
        except (InvalidBotIdError, BotNotFoundError, UnreadableBotError):
            return None
        return BotSnapshot.of(stored.bot, bot_progress(stored))
