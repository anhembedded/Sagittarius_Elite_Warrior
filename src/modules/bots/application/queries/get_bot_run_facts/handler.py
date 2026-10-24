"""`EPIC-048B` — handler for `GetBotRunFactsQuery`: the Run step's host facts of one bot.

The facts the Bots screen used to read itself, on the UI thread, from the desktop's own trading
ports (DERISK §8.1): whether the venue trades the bot's market and is on, who else holds the
symbol's lease, which other bots hold the symbol, fill the venue or wait to recover on it, and
the budget caps. The other bots are read from the store here, in the order the list shows them
(`listed`), so a host that runs the bots answers for its own bots. Every fact is read locally;
nothing reaches the exchange.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_bot_run_facts.query import (
    GetBotRunFactsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.list_bots.handler import (
    listed,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.other_active_bot import (
    BotSlot,
    occupancy_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.readiness.bot_run_facts import (
    BotRunFactsReader,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.run_facts import BotRunFacts
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerBudgetCaps,
)


class GetBotRunFactsQueryHandler(IQueryHandler[GetBotRunFactsQuery, BotRunFacts]):
    """The host's Run facts of a bot, and the caps its budget is judged against."""

    def __init__(
        self, store: IBotStore, ports: IVenueTradingPorts, caps: OwnerBudgetCaps
    ) -> None:
        self._store = store
        self._reader = BotRunFactsReader(ports, caps)

    def execute(self, query: GetBotRunFactsQuery) -> BotRunFacts:
        reading = self._store.load_all()
        occupancy = occupancy_of(
            query.bot_id,
            query.venue,
            query.symbol,
            (
                BotSlot(
                    item.bot.bot_id.value,
                    item.bot.definition.venue,
                    item.bot.definition.symbol,
                    item.bot.state,
                )
                for item in listed(reading)
            ),
            (refused.name for refused in reading.refused),
        )
        return self._reader.host_facts(
            query.bot_id, query.venue, query.symbol, occupancy
        )
