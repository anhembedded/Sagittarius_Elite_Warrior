"""The one question the host's policies and steps ask of the bots: what is each doing (`EPIC-038D`)."""

from __future__ import annotations

from typing import cast

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_status_report import (
    BotStatusEntry,
    BotStatusReport,
    GetBotStatusReportQuery,
)


def read_bot_status(dispatcher: ICommandDispatcher) -> BotStatusReport:
    """The same read model `bot list`, `bot show` and `status` print."""
    return cast(
        BotStatusReport,
        dispatcher.dispatch(GetBotStatusReportQuery, GetBotStatusReportQuery()),
    )


def active_bots(report: BotStatusReport) -> tuple[BotStatusEntry, ...]:
    """The bots that are not at rest: they hold a ladder, a base, or a doubt."""
    return tuple(bot for bot in report.bots if not bot.is_at_rest)
