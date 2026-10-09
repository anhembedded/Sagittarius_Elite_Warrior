"""`BOT-173` — what a ladder asks of the account, from the plan alone.

@details The readiness rules compare these numbers with the exchange's facts
(`exchange_rules.py`). They are pure functions of a `GridPlan`, which both the
screen and the executors build with the same `plan` / `resume_plan`, so the
amount the screen says a Start needs is the amount the Start places.

  · **A start** buys its SELL levels' base at market first, out of the capital
    (the opening buy), then lays the BUY levels: it needs quote only, for the
    opening and for the BUYs. The account needs no base of its own.
  · **A resume** lays no opening buy: the SELL levels sell base the account must
    already hold free, and the BUY levels need quote.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import GridPlan

_ZERO = Decimal(0)


@dataclass(frozen=True, slots=True)
class LadderNeeds:
    """What laying the plan takes from the account, and what it was sized from."""

    #: Quote spent: the opening buy (a start) and every BUY level.
    quote: Decimal
    #: Base sold: every SELL level (a resume; a start buys its own).
    base: Decimal
    #: The price the plan was drawn at: what a leftover base is valued at.
    price: Decimal
    #: The capital the plan shares among its levels.
    capital: Decimal


def start_needs(plan: GridPlan, capital: Decimal) -> LadderNeeds:
    opening = plan.opening_buy_quantity * plan.last_price
    return LadderNeeds(opening + _buy_notional(plan), _ZERO, plan.last_price, capital)


def resume_needs(plan: GridPlan, capital: Decimal) -> LadderNeeds:
    selling = sum((level.quantity for level in plan.sell_levels), _ZERO)
    return LadderNeeds(_buy_notional(plan), selling, plan.last_price, capital)


def _buy_notional(plan: GridPlan) -> Decimal:
    return sum((level.notional for level in plan.buy_levels), _ZERO)
