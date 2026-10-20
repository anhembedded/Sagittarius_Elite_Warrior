"""`EPIC-040C` — a sandbox judged by the symbol's rules, never by the account.

The kind's own `IBotKind.validate` does the judging (`bot_plan_judge.judge`), with no account. Tick,
step, minimum notional, fees and the venue's exposure limits still refuse a plan the exchange would
refuse. What needs the account cannot run: the key's permission to trade, and the orders already open
on the symbol (a fact of the real account, left out of the market view). Those verdicts are the
domain's own and are not changed; the Backtest tab *says* about them "not checked in a simulation"
(`sandbox_line`), so a verdict that did not run is never read as a pass.
"""

from __future__ import annotations

from dataclasses import replace

from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market import (
    PlannerMarket,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind import IBotKind
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    exposure_limits_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.backtest.sandbox_plan import (
    SandboxPlan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    PlanRiskFacts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import Verdict
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_plan_judge import (
    JudgedPlan,
    PlanWorld,
    judge,
    verdict_line,
)

#: The verdict codes about the real account, and what each is a check of: they cannot run in a
#: simulation.
ACCOUNT_CHECKS = {
    "KEY_NOT_READ": "the key's permission to trade",
    "FOREIGN_ORDERS_NOT_READ": "the orders already open on the symbol",
}


def judge_sandbox(
    kind: IBotKind,
    plan: SandboxPlan,
    market: PlannerMarket | None,
    risk: PlanRiskFacts | None = None,
) -> JudgedPlan:
    """@brief `plan` judged against the symbol's terms and the venue's limits, with no account and
    no view of the account's open orders."""
    if market is not None and market.market is not None:
        market = replace(
            market, market=replace(market.market, foreign_open_orders=None)
        )
    world = PlanWorld(
        account=None,
        limits=exposure_limits_of(plan.venue, kind.supported_profiles()),
        risk=risk,
    )
    return judge(kind, plan.config, market, world)


def sandbox_line(verdict: Verdict) -> str:
    """One verdict as the Backtest tab writes it: a check about the account says so in a few words."""
    check = ACCOUNT_CHECKS.get(verdict.code)
    if check is None:
        return verdict_line(verdict)
    return verdict_line(
        replace(verdict, reason=f"Not checked in a simulation: {check}")
    )
