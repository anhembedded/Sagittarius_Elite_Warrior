"""`bot export`: a plan written from the stored bots (`EPIC-038I`).

The inverse of apply: `export` then `apply --dry-run` is "no changes" (a test locks it).
Each bot's `desired_state` is what the record says the operator wants, or, with no record,
what the bot is doing now (the same rule the differ uses), so an exported running bot
stays wanted running.
"""

from __future__ import annotations

from collections.abc import Sequence

from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.bot_plan_document import (
    BotPlanDocument,
    PlannedBot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.plan_differ import (
    desired_state_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.applied_plan import (
    AppliedPlan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)


class UnknownBotsError(LookupError):
    """Some asked-for ids name no stored bot."""


def export_plan(
    bots: Sequence[BotSnapshot], recorded: AppliedPlan | None, ids: Sequence[str]
) -> BotPlanDocument:
    """Every bot when `ids` is empty, else exactly those.

    @raise UnknownBotsError An id in `ids` names no bot (nothing is exported).
    """
    chosen = list(bots)
    if ids:
        known = {bot.bot_id for bot in bots}
        missing = [bot_id for bot_id in ids if bot_id not in known]
        if missing:
            raise UnknownBotsError(f"no bot has the id {', '.join(missing)}")
        chosen = [bot for bot in bots if bot.bot_id in set(ids)]
    return BotPlanDocument(
        tuple(
            PlannedBot(
                name=bot.name.strip(),
                kind=bot.kind,
                venue=bot.venue,
                symbol=bot.symbol,
                desired_state=desired_state_of(bot, recorded),
                params=bot.config,
            )
            for bot in chosen
        )
    )
