"""`BOT-187` — `bot order <id>`: the orders a bot's file records, read-only.

It reads through `GetBotQuery`, the query the Bots tab reads a bot through, so the tab and this
verb show one record; it asks the exchange nothing and places, cancels and amends nothing.
Live open orders would need an order session (credentials, the venue's call budget) and a
process that holds the data root; they are a later source, not this verb (`BOT-187` follow-up).

@par Extension cases
  · live open orders - a second source behind the same report, chosen by a flag; the payload's
    `source` already names which one produced the rows.
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
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_bot import (
    GetBotQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.cli.bot_order_reports import (
    bot_order_report,
    unreadable_order_report,
)
from Sagittarius_Elite_Warrior.src.modules.bots.cli.bot_verb_world import BotVerbWorld
from Sagittarius_Elite_Warrior.src.modules.bots.cli.i_bot_verb import IBotVerb
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_status_report import (
    BotStatusReport,
    GetBotStatusReportQuery,
)


def _status_of(dispatcher: ICommandDispatcher, bot_id: str) -> BotStatusReport:
    return cast(
        BotStatusReport,
        dispatcher.dispatch(GetBotStatusReportQuery, GetBotStatusReportQuery(bot_id)),
    )


class OrderBotVerb(IBotVerb):
    name = "order"

    def run(
        self,
        args: argparse.Namespace,
        world: BotVerbWorld,
    ) -> CliOutcome | None:
        snapshot = cast(
            "BotSnapshot | None",
            world.dispatcher.dispatch(GetBotQuery, GetBotQuery(args.bot_id)),
        )
        # The status query also says whether a copy of the app holds the data root, and
        # names a refused file, which `GetBotQuery` hides as "no such bot".
        status = _status_of(world.dispatcher, args.bot_id)
        if snapshot is not None:
            return world.printer.print_report(
                bot_order_report(snapshot, app_running=status.app_running), args
            )
        if not status.unreadable:
            return CliOutcome(ExitCode.USAGE, f"No bot has the id {args.bot_id!r}.")
        return world.printer.print_report(
            unreadable_order_report(
                status.unreadable[0], app_running=status.app_running
            ),
            args,
        )
