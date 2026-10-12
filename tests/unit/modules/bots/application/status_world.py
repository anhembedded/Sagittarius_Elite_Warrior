"""`EPIC-038C` — a dispatcher that runs the bots module's real read handlers over a store.

The app's dispatcher resolves `ListBotsQuery` and `GetBotQuery` to these same
handlers (`composition/query_bindings.py`); only the store behind them is the
in-memory one, which passes the same contract suite as the JSON store.
"""

from __future__ import annotations

from pathlib import Path

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_bot import (
    GetBotQuery,
    GetBotQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_bot_status_report import (
    BotsStateDirectory,
    GetBotStatusReportQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.list_bots import (
    ListBotsQuery,
    ListBotsQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_status_report import (
    GetBotStatusReportQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_store import (
    FakeBotStore,
)

BOTS_DIRECTORY = Path("/data/state/bots")


class BotQueryDispatcher(ICommandDispatcher):
    """Routes the three bot reads to their real handlers; records what was asked."""

    def __init__(self, store: FakeBotStore) -> None:
        self.asked: list[type] = []
        self._handlers: dict[type, IQueryHandler] = {
            ListBotsQuery: ListBotsQueryHandler(store),
            GetBotQuery: GetBotQueryHandler(store),
            GetBotStatusReportQuery: GetBotStatusReportQueryHandler(
                self, BotsStateDirectory(BOTS_DIRECTORY)
            ),
        }

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        self.asked.append(handler_class)
        return self._handlers[handler_class].execute(input_dto)
