"""The verbs of the `bot` command, one class each (`EPIC-038C`, decision D3).

**Seam now, variant later.** A verb is a class registered in `BOT_VERBS`; the
handler (`bot_cli_handler.py`) looks one up by the word the operator typed and
knows none by name. `start`, `stop`, `pause` and `resume` are further classes and
further entries, plus their rows in `cli_commands.json`; they dispatch the command the
Bots tab dispatches, through the same `ICommandDispatcher`. `apply` and `export`
(`EPIC-038I`, `bot_plan_verbs.py`) are such entries already. `stop`, `pause`, `resume`, `start` and `edit`
(`EPIC-038J`/`EPIC-038K`/`EPIC-038L`, `bot_control_verbs.py`) are entries of another kind: the running host holds the
data root, so they ask it, through `IHostControl`, and the host dispatches the command.

Reads dispatch `GetBotStatusReportQuery`, whose handler is built from the Bots
tab's own queries, so the tab and these verbs read one world.

@par Extension cases
  · a new read verb (`bot fills`) — one `IBotVerb` and one entry in `BOT_VERBS`;
  · a mutating verb — the same, dispatching its command object; its
    `cli_commands.json` entry does not say `read_only`, so the entry point takes
    the writable lock for it (`support/cli_host/command_access.py`).
"""

from __future__ import annotations

import argparse
from typing import cast

from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import (
    CliOutcome,
    ExitCode,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.report import Report
from Sagittarius_Elite_Warrior.src.modules.bots.cli.bot_control_verbs import (
    AcknowledgeLossCapVerb,
    EditBotVerb,
    PauseBotVerb,
    ResumeBotVerb,
    StartBotVerb,
    StopBotVerb,
)
from Sagittarius_Elite_Warrior.src.modules.bots.cli.bot_order_verbs import (
    OrderBotVerb,
)
from Sagittarius_Elite_Warrior.src.modules.bots.cli.bot_plan_verbs import (
    ApplyBotPlanVerb,
    ExportBotPlanVerb,
)
from Sagittarius_Elite_Warrior.src.modules.bots.cli.bot_status_reports import (
    bot_list_report,
    bot_show_grids_parameters_report,
    bot_show_grids_report,
    bot_show_parameters_report,
    bot_show_report,
)
from Sagittarius_Elite_Warrior.src.modules.bots.cli.bot_verb_world import BotVerbWorld
from Sagittarius_Elite_Warrior.src.modules.bots.cli.i_bot_verb import IBotVerb
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_status_report import (
    BotStatusReport,
    GetBotStatusReportQuery,
)


def _status_of(dispatcher: ICommandDispatcher, bot_id: str | None) -> BotStatusReport:
    return cast(
        BotStatusReport,
        dispatcher.dispatch(GetBotStatusReportQuery, GetBotStatusReportQuery(bot_id)),
    )


class ListBotsVerb(IBotVerb):
    name = "list"

    def run(
        self,
        args: argparse.Namespace,
        world: BotVerbWorld,
    ) -> CliOutcome | None:
        return world.printer.print_report(
            bot_list_report(_status_of(world.dispatcher, None)), args
        )


def _show_report(status: BotStatusReport, args: argparse.Namespace) -> Report:
    """`bot show`, with the parameters (`--params`) and the grids (`--grids`) when asked for."""
    params = getattr(args, "params", False)
    if getattr(args, "grids", False):
        return (
            bot_show_grids_parameters_report(status)
            if params
            else bot_show_grids_report(status)
        )
    return bot_show_parameters_report(status) if params else bot_show_report(status)


class ShowBotVerb(IBotVerb):
    name = "show"

    def run(
        self,
        args: argparse.Namespace,
        world: BotVerbWorld,
    ) -> CliOutcome | None:
        status = _status_of(world.dispatcher, args.bot_id)
        if status.is_empty:
            return CliOutcome(ExitCode.USAGE, f"No bot has the id {args.bot_id!r}.")
        return world.printer.print_report(_show_report(status, args), args)


BOT_VERBS: tuple[IBotVerb, ...] = (
    ListBotsVerb(),
    ShowBotVerb(),
    OrderBotVerb(),
    ApplyBotPlanVerb(),
    ExportBotPlanVerb(),
    StopBotVerb(),
    PauseBotVerb(),
    ResumeBotVerb(),
    StartBotVerb(),
    EditBotVerb(),
    AcknowledgeLossCapVerb(),
)
