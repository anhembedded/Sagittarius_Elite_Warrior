"""`bot` at the command line and at the prompt (`EPIC-038C`): picks the verb, runs it.

The handler holds no verb by name (`BOT_VERBS` does), so a new verb is not an
edit here.
"""

from __future__ import annotations

import argparse

from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import (
    CliOutcome,
    ExitCode,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_cli_command_handler import (
    ICliCommandHandler,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_host_control import IHostControl
from Sagittarius_Elite_Warrior.src.core.contracts.i_instance_access import (
    IInstanceAccess,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_report_printer import (
    IReportPrinter,
)
from Sagittarius_Elite_Warrior.src.modules.bots.cli.bot_verb_world import BotVerbWorld
from Sagittarius_Elite_Warrior.src.modules.bots.cli.bot_verbs import BOT_VERBS
from Sagittarius_Elite_Warrior.src.modules.bots.cli.lazy_host_control import (
    LazyHostControl,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_applied_plan_store import (
    IAppliedPlanStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind_catalog import (
    IBotKindCatalog,
)
from sagittarius_engine import App


class BotCliHandler(ICliCommandHandler):
    """`bot list`, `bot show <id>`, `bot apply <plan>`, `bot export`, `bot stop|pause|resume <id>`."""

    @staticmethod
    def handle(args: argparse.Namespace, app: App) -> CliOutcome | None:
        verbs = {verb.name: verb for verb in BOT_VERBS}
        verb = verbs.get(getattr(args, "action", None) or "")
        if verb is None:
            return CliOutcome(
                ExitCode.USAGE, f"bot needs one of: {', '.join(sorted(verbs))}"
            )
        container = app.container
        return verb.run(
            args,
            BotVerbWorld(
                dispatcher=container.resolve(ICommandDispatcher),
                printer=container.resolve(IReportPrinter),
                kinds=container.resolve(IBotKindCatalog),
                plans=container.resolve(IAppliedPlanStore),
                instance=container.resolve(IInstanceAccess),
                host_control=LazyHostControl(lambda: container.resolve(IHostControl)),
            ),
        )
