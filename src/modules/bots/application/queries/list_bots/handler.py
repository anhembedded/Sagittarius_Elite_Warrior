"""`EPIC-029B` — handler for `ListBotsQuery`."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.list_bots.query import (
    ListBotsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.list_bots.result import (
    BotList,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore


class ListBotsQueryHandler(IQueryHandler[ListBotsQuery, BotList]):
    """Every stored bot as a snapshot, oldest first, plus the refused files."""

    def __init__(self, store: IBotStore) -> None:
        self._store = store

    def execute(self, query: ListBotsQuery) -> BotList:
        reading = self._store.load_all()
        bots = sorted(
            (stored.bot for stored in reading.bots),
            key=lambda bot: (bot.created_at, bot.bot_id.value),
        )
        return BotList(tuple(BotSnapshot.of(bot) for bot in bots), reading.refused)
