"""What a `bot` verb is given to work with (`EPIC-038I`).

The verbs are stateless classes in `BOT_VERBS`; the handler builds one `BotVerbWorld` from
the container and passes it to whichever verb the operator named. A verb takes from it only
what it needs - `list` and `show` the dispatcher and the printer, `apply` and `export` the
kind catalog, the applied-plan record and this copy's access - so a new collaborator is a
field here and no verb that ignores it changes.
"""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_instance_access import (
    IInstanceAccess,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_report_printer import (
    IReportPrinter,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_applied_plan_store import (
    IAppliedPlanStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind_catalog import (
    IBotKindCatalog,
)


@dataclass(frozen=True, slots=True)
class BotVerbWorld:
    dispatcher: ICommandDispatcher
    printer: IReportPrinter
    kinds: IBotKindCatalog
    plans: IAppliedPlanStore
    instance: IInstanceAccess
