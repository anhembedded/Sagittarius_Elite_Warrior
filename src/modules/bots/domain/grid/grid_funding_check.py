"""`EPIC-039G` — the Grid's funding constraint (DESIGN §6, `FUNDING_ADVERSE`).

A position held across a funding time pays or earns the rate times its notional. The plan
opens a net position (`GridPlan.opening_quantity`, signed: long positive, short negative,
neutral none), so the rate costs the plan money when it has the same sign as that position.
The check compares what one funding interval costs the opening position with the share
(`FuturesGridThresholds.funding_adverse_share`, 25 % by default) of the profit one
completed cycle is expected to earn. It is advice: the rate changes every interval, and the
ladder's later fills move the position either way.

A check that cannot run answers OK saying so; an unreadable rate is unknown, not zero.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    FUNDING_INTERVAL,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_check_inputs import (
    GridCheckInputs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import (
    Verdict,
    VerdictSeverity,
)

_OK, _WARNING = VerdictSeverity.OK, VerdictSeverity.WARNING

_HOURS = FUNDING_INTERVAL.total_seconds() / 3600


def check_funding_adverse(inputs: GridCheckInputs) -> Verdict:
    funding = inputs.market.funding
    if funding is None:
        return Verdict(_OK, "NO_FUNDING", "This venue charges no funding")
    if funding.rate is None:
        return Verdict(
            _OK,
            "FUNDING_NOT_CHECKED",
            "The funding rate could not be read, so what it costs was not judged",
        )
    plan = inputs.plan
    net_notional = plan.opening_quantity * plan.last_price
    # Positive: the position pays. A long pays a positive rate, a short a negative one.
    cost = net_notional * funding.rate
    limit = (
        inputs.thresholds.futures.funding_adverse_share
        * inputs.derived.cycle_profit_quote
    )
    numbers = {
        "funding_rate": funding.rate,
        "cost_per_interval": cost,
        "cycle_profit": inputs.derived.cycle_profit_quote,
        "share": inputs.thresholds.futures.funding_adverse_share,
    }
    if cost > limit and cost > 0:
        return Verdict(
            _WARNING,
            "FUNDING_ADVERSE",
            f"At the current rate ({funding.rate:.4%} per {_HOURS:.0f} h) the opening "
            f"position pays {cost:.4f} per funding time, more than "
            f"{inputs.thresholds.futures.funding_adverse_share:.0%} of the "
            f"{inputs.derived.cycle_profit_quote:.4f} one cycle is expected to earn",
            numbers,
        )
    return Verdict(
        _OK, "FUNDING", "Funding costs the opening position little or nothing", numbers
    )
