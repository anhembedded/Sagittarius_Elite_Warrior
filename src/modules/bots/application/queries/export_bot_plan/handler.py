"""`BOT-176` — handler for `ExportBotPlanQuery`: the one place a plan document is assembled.

Shared by `bot export` (`cli/bot_plan_verbs.py`) and the desktop's Export plan…, so the two
write the same text for the same stored state.
"""

from __future__ import annotations

from dataclasses import replace
from typing import cast

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.bot_plan_document import (
    BotPlanDocument,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.plan_export import (
    export_plan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.export_bot_plan.query import (
    ExportBotPlanQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.list_bots import (
    BotList,
    ListBotsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.applied_plan import (
    AppliedPlan,
    AppliedPlanUnreadableError,
    DesiredState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_applied_plan_store import (
    IAppliedPlanStore,
)


class ExportBotPlanQueryHandler(IQueryHandler[ExportBotPlanQuery, BotPlanDocument]):
    """The chosen bots as a plan document.

    @raise UnknownBotsError An id in the query names no stored bot.
    """

    def __init__(
        self, dispatcher: ICommandDispatcher, plans: IAppliedPlanStore
    ) -> None:
        self._dispatcher = dispatcher
        self._plans = plans

    def execute(self, query: ExportBotPlanQuery) -> BotPlanDocument:
        listing = cast(
            BotList, self._dispatcher.dispatch(ListBotsQuery, ListBotsQuery())
        )
        document = export_plan(listing.bots, self._recorded(), query.bot_ids)
        if not query.all_stopped:
            return document
        return BotPlanDocument(
            tuple(
                replace(bot, desired_state=DesiredState.STOPPED)
                for bot in document.bots
            )
        )

    def _recorded(self) -> AppliedPlan | None:
        """An unreadable record counts as none: the export then reads what each bot does."""
        try:
            return self._plans.read()
        except AppliedPlanUnreadableError:
            return None
