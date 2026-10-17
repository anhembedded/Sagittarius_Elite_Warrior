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
from Sagittarius_Elite_Warrior.src.core.contracts.i_instance_access import (
    IInstanceAccess,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_instance_probe import (
    IInstanceProbe,
)
from Sagittarius_Elite_Warrior.src.infrastructure.single_instance.instance_access import (
    InstanceAccess,
)
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
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_kind_catalog import (
    BotKindCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_status_report import (
    GetBotStatusReportQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_clock import IBotClock
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind_catalog import (
    IBotKindCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_clock import (
    FakeBotClock,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_store import (
    FakeBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_kind import GridKind
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
)

BOTS_DIRECTORY = Path("/data/state/bots")


class HeldProbe(IInstanceProbe):
    """Whether some copy holds the data root, as the test says."""

    def __init__(self, held: bool = True) -> None:
        self.held = held

    def is_held(self) -> bool:
        return self.held


class BotQueryDispatcher(ICommandDispatcher):
    """Routes the three bot reads to their real handlers; records what was asked."""

    def __init__(
        self,
        store: FakeBotStore,
        probe: IInstanceProbe | None = None,
        instance: IInstanceAccess | None = None,
        kinds: IBotKindCatalog | None = None,
        clock: IBotClock | None = None,
    ) -> None:
        self.asked: list[type] = []
        self._handlers: dict[type, IQueryHandler] = {
            ListBotsQuery: ListBotsQueryHandler(store),
            GetBotQuery: GetBotQueryHandler(store),
            GetBotStatusReportQuery: GetBotStatusReportQueryHandler(
                self,
                BotsStateDirectory(BOTS_DIRECTORY),
                probe or HeldProbe(),
                instance or InstanceAccess.declined("a reader"),
                kinds or BotKindCatalog([GridKind(None, GridThresholds())]),  # type: ignore[arg-type]
                clock or FakeBotClock(),
            ),
        }

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        self.asked.append(handler_class)
        return self._handlers[handler_class].execute(input_dto)
