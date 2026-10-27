"""`EPIC-048B` — handler for `ExportBotPlanToFileCommand`: the plan document, written to a new file.

The document is `ExportBotPlanQuery`'s, so the desktop's Export plan… and `bot export` write the
same text for the same stored state, and the file is `IPlanFileWriter`'s, which never overwrites.
The ids are checked before the query is dispatched: the engine's dispatcher logs a raising
handler at ERROR, and a mistyped id is a refusal, not a failure.
"""

from __future__ import annotations

from typing import cast

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.bot_plan_document import (
    BotPlanDocument,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.plan_export import (
    UnknownBotsError,
    require_known_bots,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.export_bot_plan import (
    ExportBotPlanQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.list_bots import (
    BotList,
    ListBotsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.export_bot_plan_to_file.command import (
    ExportBotPlanToFileCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.export_bot_plan_to_file.result import (
    PlanFileExport,
    PlanFileExported,
    PlanFileNotExported,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_plan_file_writer import (
    IPlanFileWriter,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.plan_file import (
    PlanFileRefused,
)


class ExportBotPlanToFileCommandHandler(
    ICommandHandler[ExportBotPlanToFileCommand, PlanFileExport]
):
    def __init__(self, dispatcher: ICommandDispatcher, writer: IPlanFileWriter) -> None:
        self._dispatcher = dispatcher
        self._writer = writer

    def execute(self, command: ExportBotPlanToFileCommand) -> PlanFileExport:
        listing = cast(
            BotList, self._dispatcher.dispatch(ListBotsQuery, ListBotsQuery())
        )
        try:
            require_known_bots(listing.bots, command.bot_ids)
        except UnknownBotsError as unknown:
            return PlanFileNotExported(command.path, "unknown_bots", str(unknown))
        document = cast(
            BotPlanDocument,
            self._dispatcher.dispatch(
                ExportBotPlanQuery,
                ExportBotPlanQuery(command.bot_ids, all_stopped=command.all_stopped),
            ),
        )
        written = self._writer.write_new(command.path, document.to_json_text())
        if isinstance(written, PlanFileRefused):
            return PlanFileNotExported(command.path, written.reason, written.detail)
        return PlanFileExported(command.path, len(document.bots))
