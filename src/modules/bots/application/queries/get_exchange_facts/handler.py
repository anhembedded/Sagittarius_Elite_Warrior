"""`BOT-173` — handler for `GetExchangeFactsQuery`: the exchange snapshot of one bot.

A bot that cannot be found or read is an unavailable snapshot, in the words every
bot command refuses it with, so the screen has one thing to show for it.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_exchange_facts.query import (
    GetExchangeFactsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_lookup import (
    BotLookup,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.exchange_facts_reader import (
    ExchangeFactsReader,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.exchange_facts import (
    ExchangeSnapshot,
    ExchangeUnavailable,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore


class GetExchangeFactsQueryHandler(
    IQueryHandler[GetExchangeFactsQuery, ExchangeSnapshot]
):
    def __init__(self, store: IBotStore, reader: ExchangeFactsReader) -> None:
        self._lookup = BotLookup(store)
        self._reader = reader

    def execute(self, query: GetExchangeFactsQuery) -> ExchangeSnapshot:
        found = self._lookup.find(query.bot_id)
        if isinstance(found, BotCommandResult):
            return ExchangeUnavailable(found.message)
        return self._reader.read(found.bot)
