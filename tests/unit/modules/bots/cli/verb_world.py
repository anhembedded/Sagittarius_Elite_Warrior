"""A `BotVerbWorld` for a verb's unit test (`EPIC-038C`, `EPIC-038I`)."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_instance_access import (
    IInstanceAccess,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_report_printer import (
    IReportPrinter,
)
from Sagittarius_Elite_Warrior.src.infrastructure.single_instance.instance_access import (
    InstanceAccess,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_kind_catalog import (
    BotKindCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.bots.cli.bot_verb_world import BotVerbWorld
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_applied_plan_store import (
    IAppliedPlanStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind_catalog import (
    IBotKindCatalog,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.plan.plan_world import (
    MemoryAppliedPlanStore,
    StubKind,
)


def verb_world(
    dispatcher: ICommandDispatcher,
    printer: IReportPrinter,
    *,
    kinds: IBotKindCatalog | None = None,
    plans: IAppliedPlanStore | None = None,
    instance: IInstanceAccess | None = None,
) -> BotVerbWorld:
    """A writable copy with a `grid` kind and an empty record, unless the test says otherwise."""
    return BotVerbWorld(
        dispatcher=dispatcher,
        printer=printer,
        kinds=kinds if kinds is not None else BotKindCatalog([StubKind("grid")]),
        plans=plans if plans is not None else MemoryAppliedPlanStore(),
        instance=instance if instance is not None else InstanceAccess.unguarded(),
    )
