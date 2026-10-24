"""`EPIC-029B` — handler for `ListBotsQuery`."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.list_bots.query import (
    ListBotsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.list_bots.result import (
    BotList,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.readiness.bot_progress_reader import (
    bot_progress,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import (
    BotStoreReading,
    IBotStore,
    StoredBot,
)


class ListBotsQueryHandler(IQueryHandler[ListBotsQuery, BotList]):
    """Every stored bot as a snapshot, oldest first, plus the refused files."""

    def __init__(self, store: IBotStore) -> None:
        self._store = store

    def execute(self, query: ListBotsQuery) -> BotList:
        reading = self._store.load_all()
        return BotList(
            tuple(
                BotSnapshot.of(item.bot, bot_progress(item)) for item in listed(reading)
            ),
            reading.refused,
        )


def listed(reading: BotStoreReading) -> tuple[StoredBot, ...]:
    """The stored bots in the order the list shows them: oldest first. Who holds a symbol, and
    which bots fill a venue, are named in this order too (`GetBotRunFactsQuery`)."""
    return tuple(
        sorted(
            reading.bots,
            key=lambda item: (item.bot.created_at, item.bot.bot_id.value),
        )
    )
