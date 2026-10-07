"""`EPIC-029F` — everything the detail panel shows for the selected bot, in
one pure computation: its figures, the kind's verdicts on the parameters on
screen, what is left before Start, which actions are live, and the overlay to
draw.

The parameters judged are the edited ones while the user edits, else the
saved ones: **Save and start** (`EPIC-034H`, D8) saves the edits and starts, so
what is judged is what would run. What is left before Start is
`assess_readiness`, the function the Start use case asks as well.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market import (
    PlannerMarket,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.readiness_assessment import (
    ConnectionRead,
    ConnectionState,
    ReadinessInputs,
    RunFacts,
    assess_readiness,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_readiness import (
    BotReadiness,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind import IBotKind
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    RUN_STARTING_STATES,
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
    #: What the Connect step answered (`EPIC-034D`); `None` before it asked.
    connection: ConnectionRead | None = None
    #: The Run step's facts (`EPIC-034H`).
    run: RunFacts = field(default_factory=RunFacts)


@dataclass(frozen=True)
class BotDetail:
    facts: BotFacts
    verdicts: tuple[Verdict, ...]
    verdict_lines: tuple[str, ...]
    availability: Mapping[BotAction, ActionAvailability]
    overlay: BotOverlay | None
    #: What is left before Start, for a bot that is at rest; `None` for one
    #: that already has a run, whose Start is not a next step.
    readiness: BotReadiness | None


def detail_for(inputs: DetailInputs) -> BotDetail:
    bot = inputs.bot
    config = inputs.edited if inputs.edited is not None else bot.config
    connection = inputs.connection or ConnectionRead(ConnectionState.READING, "")
    judged = (
        judge(inputs.kind, config, inputs.market, connection.account)
        if inputs.kind is not None
        else JudgedPlan()
    )
    readiness = (
        assess_readiness(
            ReadinessInputs(
                inputs.kind,
                bot.kind,
                bot.symbol,
                config,
                connection,
                inputs.market,
                inputs.run,
            )
        )
        if bot.state in RUN_STARTING_STATES
        else None
    )
    start = StartConditions(
        blocked_by=readiness.message() if readiness and not readiness.can_start else ""
    )
    return BotDetail(
        facts=bot_facts(bot, inputs.last_price, inputs.now),
        verdicts=judged.verdicts,
        verdict_lines=tuple(verdict_line(verdict) for verdict in judged.verdicts),
        availability={
            action: availability(bot.state, action, start) for action in BotAction
        },
        overlay=judged.overlay,
        readiness=readiness,
    )
