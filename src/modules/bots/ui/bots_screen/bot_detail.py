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
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.exchange_rules import (
    field_verdicts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.readiness_assessment import (
    MARKET_NOT_READ,
    ConnectionRead,
    ConnectionState,
    ReadinessInputs,
    RunFacts,
    assess_readiness,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.resume_readiness import (
    ResumeInputs,
    assess_resume,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_readiness import (
    BotReadiness,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.exchange_facts import (
    ExchangeChecking,
    ExchangeSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind import IBotKind
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    RUN_STARTING_STATES,
    BotLifecycleState,
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerInventory,
)


@dataclass(frozen=True)
class DetailInputs:
    bot: BotSnapshot
    #: `None` when no kind in the catalog has the bot's `kind_id`.
    kind: IBotKind | None
    market: PlannerMarket | None
    now: datetime
    #: The parameters on screen when they differ from the saved ones.
    edited: Mapping[str, str] | None = None
    #: What the Connect step answered (`EPIC-034D`); `None` before it asked.
    connection: ConnectionRead | None = None
    #: The Run step's facts (`EPIC-034H`).
    run: RunFacts = field(default_factory=RunFacts)
    #: What the exchange says (`BOT-174`); still being asked until it answers.
    exchange: ExchangeSnapshot = field(default_factory=ExchangeChecking)


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
    #: Why no grid is drawn on the chart of a bot at rest ("Grid not drawn: …"),
    #: empty when one is (`EPIC-035N`).
    overlay_note: str = ""


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
                inputs.exchange,
            )
        )
        if bot.state in RUN_STARTING_STATES
        else None
    )
    start = StartConditions(
        blocked_by=readiness.message() if readiness and not readiness.can_start else "",
        resume_blocked_by=_resume_blocked_by(inputs),
    )
    verdicts = judged.verdicts + (field_verdicts(readiness.items) if readiness else ())
    return BotDetail(
        facts=bot_facts(bot, inputs.now),
        verdicts=verdicts,
        verdict_lines=tuple(verdict_line(verdict) for verdict in verdicts),
        availability={
            action: availability(bot.state, action, start) for action in BotAction
        },
        overlay=judged.overlay,
        readiness=readiness,
        overlay_note=_not_drawn(bot, inputs.market, judged),
    )


def _resume_blocked_by(inputs: DetailInputs) -> str:
    """What the exchange's facts leave in a HALTED bot's Resume's way (`BOT-174`):
    the same rules and words the Resume use case refuses with."""
    bot, market = inputs.bot, inputs.market
    if bot.state is not BotLifecycleState.HALTED:
        return ""
    left = assess_resume(
        ResumeInputs(
            inputs.edited if inputs.edited is not None else bot.config,
            market,
            _recorded_inventory(bot),
            inputs.exchange,
        )
    ).items
    return (
        "Resume is blocked: " + "; ".join(item.reason for item in left) if left else ""
    )


def _recorded_inventory(bot: BotSnapshot) -> OwnerInventory:
    """What the bot's own record says it holds, and what that cost."""
    progress = bot.progress
    if progress is None:
        return OwnerInventory(Decimal(0), Decimal(0))
    return OwnerInventory(progress.inventory, progress.cost)


def _not_drawn(
    bot: BotSnapshot, market: PlannerMarket | None, judged: JudgedPlan
) -> str:
    """Why a bot at rest has no grid on its chart: the plan that is judged and
    drawn is the one a Start would place, so the reason is the first thing that
    refuses it, or that the market numbers are not read yet."""
    if bot.state not in RUN_STARTING_STATES:
        return ""
    if judged.overlay is not None and judged.overlay.lines:
        return ""
    if market is None or market.terms is None or market.market is None:
        return f"Grid not drawn: {MARKET_NOT_READ[0].lower()}{MARKET_NOT_READ[1:]}"
    refusing = next((v for v in judged.verdicts if v.refuses), None)
    if refusing is not None:
        return f"Grid not drawn: {refusing.reason}"
    return "Grid not drawn: the parameters do not make a plan yet"
