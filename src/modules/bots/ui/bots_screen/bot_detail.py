"""`EPIC-029F` — everything the detail panel shows for the selected bot, in
one pure computation: its figures, the kind's verdicts on the parameters on
screen, what is left before Start, which actions are live, and the overlay to
draw.

The parameters judged are the edited ones while the user edits, else the
saved ones: **Save and start** (`EPIC-034H`, D8) saves the edits and starts, so
what is judged is what would run. What is left before Start is
`assess_readiness`, the function the Start use case asks as well, reached through
`AssessBotQuery` (`EPIC-048B`): the screen imports no application internal, and the query reads
nothing, so a re-judge never waits on a host.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime

from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.assess_bot import (
    AssessBotQuery,
    BotAssessment,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market import (
    PlannerMarket,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_readiness import (
    MARKET_NOT_READ,
    BotReadiness,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.connection_read import (
    ConnectionRead,
    ConnectionState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.exchange_facts import (
    ExchangeChecking,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.futures_facts import (
    VenueSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.grid_ladder import (
    GridLadder,
    LadderUnavailable,
    grid_ladder_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind import IBotKind
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.run_facts import BotRunFacts
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    exposure_limits_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    BotKindInputs,
    PlanRiskFacts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    RUN_STARTING_STATES,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_overlay import BotOverlay
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_exit_estimate import (
    ExitEstimates,
    exit_estimates_for,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_kind import (
    GRID_KIND_ID,
    GRID_MARKETS,
)
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
    PlanWorld,
    judge,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.exit_estimate_words import (
    exit_rows,
    rows_cut_by_liquidation,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.plan_checks import (
    PlanChecks,
    plan_checks_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.plan_trigger_line import (
    shown_for,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.grid_liquidation import (
    liquidation_lines,
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
    #: The host's Run facts (`EPIC-034H`, `GetBotRunFactsQuery`); `None` while they are being
    #: read, which leaves Start waiting for them.
    run: BotRunFacts | None = None
    #: What the exchange says (`BOT-174`); still being asked until it answers.
    exchange: VenueSnapshot = field(default_factory=ExchangeChecking)
    #: The symbol's liquidation facts on a position venue (`EPIC-039J`); `None` until read.
    risk: PlanRiskFacts | None = None


@dataclass(frozen=True)
class BotDetail:
    facts: BotFacts
    verdicts: tuple[Verdict, ...]
    checks: PlanChecks
    availability: Mapping[BotAction, ActionAvailability]
    overlay: BotOverlay | None
    #: What is left before Start, for a bot that is at rest; `None` for one
    #: that already has a run, whose Start is not a next step.
    readiness: BotReadiness | None
    #: Why no grid is drawn on the chart of a bot at rest ("Grid not drawn: …"),
    #: empty when one is (`EPIC-035N`).
    overlay_note: str = ""
    #: The ladder the parameters on screen make (the saved ones when nothing is edited), with what
    #: the saved run records (`BOT-193`, `BUG-261`).
    ladder: GridLadder | LadderUnavailable | None = None


#: The door to the pure assessment (`AssessBotQuery`, `EPIC-048B`): the screen sends the query
#: through its dispatcher; a test may hand the handler's `execute` itself.
type Assess = Callable[[AssessBotQuery], BotAssessment]


def detail_for(inputs: DetailInputs, assess: Assess) -> BotDetail:
    bot = inputs.bot
    config = inputs.edited if inputs.edited is not None else bot.config
    connection = inputs.connection or ConnectionRead(ConnectionState.READING, "")
    judged = (
        judge(
            inputs.kind,
            config,
            inputs.market,
            PlanWorld(
                connection.account,
                exposure_limits_of(bot.venue, GRID_MARKETS),
                inputs.risk,
            ),
        )
        if inputs.kind is not None
        else JudgedPlan()
    )
    assessed = assess(
        AssessBotQuery(
            bot,
            inputs.kind,
            config,
            connection,
            inputs.market,
            inputs.run,
            inputs.exchange,
        )
    )
    readiness = assessed.readiness
    start = StartConditions(
        blocked_by=readiness.message() if readiness and not readiness.can_start else "",
        resume_blocked_by=assessed.resume_blocked_by,
    )
    verdicts = judged.verdicts + assessed.field_verdicts
    # `BUG-261`: the plan figures read the design on screen, as the checks and the chart do.
    shown = bot if inputs.edited is None else replace(bot, config=config)
    facts = bot_facts(shown, inputs.now)
    estimates = _exit_estimates(inputs, config)
    exits = exit_rows(
        estimates,
        rows_cut_by_liquidation(verdicts, estimates.direction)
        if estimates is not None
        else frozenset(),
    )
    return BotDetail(
        facts=replace(
            facts,
            unsaved=inputs.edited is not None,
            # A bot at rest has no run to report its liquidation price, so it shows the guard's
            # estimate, as a design not saved yet does (`BUG-261`, `BOT-235`).
            liquidation_estimate=(
                "; ".join(line.text for line in liquidation_lines(verdicts))
                if inputs.edited is not None or bot.state in RUN_STARTING_STATES
                else ""
            ),
            loss_at_stop=exits.loss_at_stop,
            gain_at_take_profit=exits.gain_at_take_profit,
            tones={**facts.tones, **exits.tones},
        ),
        verdicts=verdicts,
        checks=plan_checks_of(verdicts),
        availability={
            action: availability(bot.state, action, start) for action in BotAction
        },
        overlay=shown_for(judged.overlay, bot),
        readiness=readiness,
        overlay_note=_not_drawn(bot, inputs.market, judged),
        ladder=grid_ladder_of(shown, inputs.now),
    )


def _exit_estimates(
    inputs: DetailInputs, config: Mapping[str, str]
) -> ExitEstimates | None:
    """What a straight run to the stop loss and to the take profit is worth, for a Grid at rest
    whose market numbers are read; `None` otherwise (`BOT-235`). A bot with a run shows none: its
    plan was drawn at the price its run began at, not at today's."""
    bot, market = inputs.bot, inputs.market
    if (
        bot.kind != GRID_KIND_ID
        or bot.state not in RUN_STARTING_STATES
        or market is None
        or market.terms is None
        or market.market is None
    ):
        return None
    return exit_estimates_for(
        BotKindInputs(
            config,
            market.terms,
            market.market,
            limits=exposure_limits_of(bot.venue, GRID_MARKETS),
        )
    )


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
