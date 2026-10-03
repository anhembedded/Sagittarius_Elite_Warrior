"""bots' read side: the list and one bot (`EPIC-029B`)."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_bot import (
    GetBotQuery,
    GetBotQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.list_bots import (
    ListBotsQuery,
    ListBotsQueryHandler,
)
from sagittarius_engine.interfaces.i_container import IContainer


def bind_queries(container: IContainer) -> None:
    container.bind(ListBotsQuery, ListBotsQueryHandler)
    container.bind(GetBotQuery, GetBotQueryHandler)
