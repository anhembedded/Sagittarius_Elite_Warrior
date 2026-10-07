"""`EPIC-029F` — everything the detail panel shows for the selected bot, in
one pure computation: its figures, the kind's verdicts on the parameters on
screen, which actions are live, and the overlay to draw.

The parameters judged are the edited ones while the user edits, else the
saved ones; Start waits for edits to be saved, since a start runs what is
saved.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market import (
    PlannerMarket,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind import IBotKind
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    AccountView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_overlay import BotOverlay
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import Verdict
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_action_rules import (
    ActionAvailability,
    BotAction,
    StartConditions,
    availability,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_facts import (
    BotFacts,
    bot_facts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_plan_judge import (
    JudgedPlan,
    judge,
    verdict_line,
)


@dataclass(frozen=True)
class DetailInputs:
    bot: BotSnapshot
    #: `None` when no kind in the catalog has the bot's `kind_id`.
    kind: IBotKind | None
    market: PlannerMarket | None
    last_price: Decimal | None
    now: datetime
    #: The parameters on screen when they differ from the saved ones.
    edited: Mapping[str, str] | None = None
    #: Why Start waits on the venue's account (`EPIC-034D`); empty when it
    #: says go.
    connection: str = ""
    #: What the Connect step read, once it did (`EPIC-034F`).
    account: AccountView | None = None


@dataclass(frozen=True)
class BotDetail:
    facts: BotFacts
    verdicts: tuple[Verdict, ...]
    verdict_lines: tuple[str, ...]
    refusal: str
    availability: Mapping[BotAction, ActionAvailability]
    overlay: BotOverlay | None


def detail_for(inputs: DetailInputs) -> BotDetail:
    bot = inputs.bot
    config = inputs.edited if inputs.edited is not None else bot.config
    judged = (
        judge(inputs.kind, config, inputs.market, inputs.account)
        if inputs.kind is not None
        else JudgedPlan(refusal=f"No kind of bot is called {bot.kind!r}.")
    )
    unsaved = inputs.edited is not None and dict(inputs.edited) != dict(bot.config)
    start = StartConditions(
        refusal=judged.refusal, unsaved_edits=unsaved, connection=inputs.connection
    )
    return BotDetail(
        facts=bot_facts(bot, inputs.last_price, inputs.now),
        verdicts=judged.verdicts,
        verdict_lines=tuple(verdict_line(verdict) for verdict in judged.verdicts),
        refusal=judged.refusal,
        availability={
            action: availability(bot.state, action, start) for action in BotAction
        },
        overlay=judged.overlay,
    )
