"""`EPIC-029F` — what the Bots screen shows about a plan, from the kind's own
judgement.

The screen never judges a plan itself: it asks the bot's kind
(`IBotKind.validate`, `IBotKind.overlay`) with the planner's market numbers,
so the verdicts shown are the ones a start would meet. The account (`EPIC-034F`) is the Connect
step's read, so the balance and the key are judged beside the rest. Pure and
quick (a Grid of a thousand levels evaluates in milliseconds), so it runs on each edit,
debounced by the presenter rather than moved off the UI thread.

A plan that cannot be judged (the market numbers are not read yet, or could
not be) has no verdicts and no overlay; what Start waits on, and why, is the
readiness's to say (`EPIC-034H`), not this module's.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market import (
    PlannerMarket,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind import IBotKind
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    SPOT_LIMITS,
    ExposureLimits,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    AccountView,
    BotKindInputs,
    PlanRiskFacts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_overlay import BotOverlay
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import (
    Verdict,
    VerdictSeverity,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import (
    write_value,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import ColumnKind


@dataclass(frozen=True, slots=True)
class JudgedPlan:
    verdicts: tuple[Verdict, ...] = ()
    #: The proposed levels to draw; `None` when there is nothing to draw.
    overlay: BotOverlay | None = None


@dataclass(frozen=True, slots=True)
class PlanWorld:
    """What a plan is judged against besides the market (`EPIC-039J`): the account the
    Connect step read, the directions and leverage the venue's market allows, and the symbol's
    risk facts once read. Spot's answer is the default: long at 1, nothing to liquidate."""

    account: AccountView | None = None
    limits: ExposureLimits = SPOT_LIMITS
    risk: PlanRiskFacts | None = None


def judge(
    kind: IBotKind,
    config: Mapping[str, str],
    market: PlannerMarket | None,
    world: PlanWorld = PlanWorld(),  # noqa: B008
) -> JudgedPlan:
    if market is None or market.terms is None or market.market is None:
        return JudgedPlan()
    inputs = BotKindInputs(
        config, market.terms, market.market, world.account, world.limits, world.risk
    )
    return JudgedPlan(verdicts=kind.validate(inputs), overlay=kind.overlay(inputs))


def verdict_line(verdict: Verdict) -> str:
    """One verdict as a line of text: its severity in words (never colour
    alone), its sentence, and the numbers behind it, so a warning shows the
    threshold beside the measured value."""
    numbers = ", ".join(
        f"{name.replace('_', ' ')} {write_value(ColumnKind.QUANTITY, value)}"
        for name, value in verdict.numbers.items()
    )
    tail = f" ({numbers})" if numbers else ""
    return f"{_LABEL[verdict.severity]}: {verdict.reason}{tail}"


_LABEL = {
    VerdictSeverity.OK: "OK",
    VerdictSeverity.WARNING: "Warning",
    VerdictSeverity.REFUSED: "Refused",
}
