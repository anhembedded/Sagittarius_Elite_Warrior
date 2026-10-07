"""bots' read side: the list and one bot (`EPIC-029B`), and the numbers a
bot's panel judges its parameters against and a bot's fills (`EPIC-029F`)."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_bot import (
    GetBotQuery,
    GetBotQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_bot_fills import (
    GetBotFillsQuery,
    GetBotFillsQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_mainnet_account import (
    GetMainnetAccountQuery,
    GetMainnetAccountQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market import (
    GetPlannerMarketQuery,
    GetPlannerMarketQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_venue_connection import (
    GetVenueConnectionQuery,
    GetVenueConnectionQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.list_bots import (
    ListBotsQuery,
    ListBotsQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.run_grid_backtest import (
    RunGridBacktestQuery,
    RunGridBacktestQueryHandler,
)
from sagittarius_engine.interfaces.i_container import IContainer


def bind_queries(container: IContainer) -> None:
    container.bind(ListBotsQuery, ListBotsQueryHandler)
    container.bind(GetBotQuery, GetBotQueryHandler)
    container.bind(GetPlannerMarketQuery, GetPlannerMarketQueryHandler)
    container.bind(GetBotFillsQuery, GetBotFillsQueryHandler)
    container.bind(GetVenueConnectionQuery, GetVenueConnectionQueryHandler)
    container.bind(GetMainnetAccountQuery, GetMainnetAccountQueryHandler)
    container.bind(RunGridBacktestQuery, RunGridBacktestQueryHandler)
