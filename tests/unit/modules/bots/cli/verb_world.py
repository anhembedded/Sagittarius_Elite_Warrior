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
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.export_bot_plan import (
    ExportBotPlanQuery,
    ExportBotPlanQueryHandler,
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


class _WithExportQuery(ICommandDispatcher):
    """The app's dispatcher resolves `ExportBotPlanQuery` to its handler over the real
    record store (`composition/query_bindings.py`); here the handler is built over the
    test's own `plans` and every other call goes to the test's dispatcher."""

    def __init__(self, inner: ICommandDispatcher, plans: IAppliedPlanStore) -> None:
        self._inner = inner
        self._export = ExportBotPlanQueryHandler(inner, plans)

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        if handler_class is ExportBotPlanQuery:
            assert isinstance(input_dto, ExportBotPlanQuery)
            return self._export.execute(input_dto)
        return self._inner.dispatch(handler_class, input_dto)


def verb_world(
    dispatcher: ICommandDispatcher,
    printer: IReportPrinter,
    *,
    kinds: IBotKindCatalog | None = None,
    plans: IAppliedPlanStore | None = None,
    instance: IInstanceAccess | None = None,
) -> BotVerbWorld:
    """A writable copy with a `grid` kind and an empty record, unless the test says otherwise."""
    record = plans if plans is not None else MemoryAppliedPlanStore()
    return BotVerbWorld(
        dispatcher=_WithExportQuery(dispatcher, record),
        printer=printer,
        kinds=kinds if kinds is not None else BotKindCatalog([StubKind("grid")]),
        plans=record,
        instance=instance if instance is not None else InstanceAccess.unguarded(),
    )
