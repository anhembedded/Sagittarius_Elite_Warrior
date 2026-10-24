"""`EPIC-048B` — handler for `AssessBotQuery`: the pure assessment of one bot, behind the doors.

What the Bots screen used to run itself (`EPIC-048` D5): `assess_readiness` for a bot at rest,
`assess_resume` for one that proposes a Resume, and the readiness items that are about a
parameter as verdicts. It reads nothing, so it is answered where the screen runs: the Plan
re-judges 150 ms after the last keystroke (`presenter_pacing.REJUDGE_MS`) and a re-judge never
waits on a link (DERISK R1 §1.5). A backend that answers the host's queries remotely answers this
one locally, as it keeps the kinds (`IBotKind`) local.

The judgement is the Start and Resume use cases' own: `assess_readiness`, `run_facts_for` and
`assess_resume` are the functions they call, so the button that is enabled is the click that is
accepted. The one difference is a Run step whose host facts are still being read: the screen
says so and Start waits, rather than judging a Start against facts nobody has read.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.assess_bot.query import (
    AssessBotQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.assess_bot.result import (
    BotAssessment,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.readiness.bot_run_facts import (
    run_facts_for,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.readiness.readiness_assessment import (
    ReadinessInputs,
    assess_readiness,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.readiness.resume_readiness import (
    ResumeInputs,
    assess_resume,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue.exchange_rules import (
    field_verdicts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_readiness import (
    READING_THE_RUN_FACTS,
    BotReadiness,
    ReadinessFix,
    ReadinessItem,
    ReadinessStep,
    StepReadiness,
    StepStatus,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.run_facts import RunFacts
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    SPOT_PROFILE,
    VenueProfile,
    bot_profile_of,
    exposure_limits_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    RESUME_PROPOSES_STATES,
    RUN_STARTING_STATES,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_kind import (
    GRID_MARKETS,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerInventory,
)

#: The code of the Run step's item while its host facts are being read.
RUN_FACTS_READING = "RUN_FACTS_READING"


class AssessBotQueryHandler(IQueryHandler[AssessBotQuery, BotAssessment]):
    """Readiness, the Resume's blocker and the parameter verdicts, from the facts given."""

    def execute(self, query: AssessBotQuery) -> BotAssessment:
        readiness = _readiness(query)
        return BotAssessment(
            readiness,
            _resume_blocked_by(query),
            field_verdicts(readiness.items) if readiness else (),
        )


def _readiness(query: AssessBotQuery) -> BotReadiness | None:
    bot = query.bot
    if bot.state not in RUN_STARTING_STATES:
        return None
    readiness = assess_readiness(
        ReadinessInputs(
            query.kind,
            bot.kind,
            bot.symbol,
            query.config,
            query.connection,
            query.market,
            run_facts_for(query.run, query.config) if query.run else RunFacts(),
            query.exchange,
            profile=_profile_of(bot),
            limits=exposure_limits_of(bot.venue, GRID_MARKETS),
        )
    )
    return readiness if query.run else _run_facts_reading(readiness, query)


def _run_facts_reading(readiness: BotReadiness, query: AssessBotQuery) -> BotReadiness:
    """The Run step waits for its host facts: one item, so Start stays disabled until they are
    read and judged."""
    item = ReadinessItem(
        ReadinessStep.RUN,
        RUN_FACTS_READING,
        f"{query.connection.venue_title}: {READING_THE_RUN_FACTS}",
        ReadinessFix.WAIT,
        BotRefusal.VENUE_NOT_READY,
    )
    return replace(
        readiness,
        steps=tuple(
            StepReadiness(step.step, StepStatus.OPEN, (*step.items, item))
            if step.step is ReadinessStep.RUN
            else step
            for step in readiness.steps
        ),
    )


def _resume_blocked_by(query: AssessBotQuery) -> str:
    """What the exchange's facts leave in a HALTED bot's Resume's way (`BOT-174`): the same rules
    and words the Resume use case refuses with."""
    bot = query.bot
    if bot.state not in RESUME_PROPOSES_STATES:
        return ""
    left = assess_resume(
        ResumeInputs(
            query.config,
            query.market,
            _recorded_inventory(bot),
            query.exchange,
            _profile_of(bot),
        )
    ).items
    return (
        "Resume is blocked: " + "; ".join(item.reason for item in left) if left else ""
    )


def _profile_of(bot: BotSnapshot) -> VenueProfile:
    """The profile of the bot's venue, which judges the exchange facts read for that venue."""
    return bot_profile_of(bot.venue, GRID_MARKETS) or SPOT_PROFILE


def _recorded_inventory(bot: BotSnapshot) -> OwnerInventory:
    """What the bot's own record says it holds, and what that cost."""
    progress = bot.progress
    if progress is None:
        return OwnerInventory(Decimal(0), Decimal(0))
    return OwnerInventory(progress.inventory, progress.cost)
