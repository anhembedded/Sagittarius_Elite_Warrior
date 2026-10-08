"""`EPIC-035L` (audit H7), owner decision D4 (a) — Start with the price outside the range.

  · `PRICE_BELOW_RANGE` (refusal) — below the lower bound every level is a SELL
    level, so the plan market-buys the base of the whole ladder before it lays
    one order, at a price under the range the user designed for;
  · `PRICE_ABOVE_RANGE` (warning) — above the upper bound every level is a BUY
    level: nothing is bought, no money is at risk, and the bot waits for a fall.

The bounds are the user's own: the plan sides a level by its raw price against
the last price (`grid_plan.py`), so these bounds are exactly where the plan
changes shape. D2 holds: nothing here mentions a stop loss.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_check_inputs import (
    GridCheckInputs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.range_position import (
    RangePosition,
    range_position,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import (
    Verdict,
    VerdictSeverity,
)

_PERCENT = Decimal(100)


def check_price_against_range(inputs: GridCheckInputs) -> Verdict:
    params, plan = inputs.params, inputs.plan
    last = plan.last_price
    opening_quote = plan.opening_buy_quantity * last
    numbers = {
        "last_price": last,
        "lower": params.lower,
        "upper": params.upper,
        "opening_quote": opening_quote,
    }
    match range_position(last, params.lower, params.upper):
        case RangePosition.BELOW:
            share = opening_quote / params.capital_quote * _PERCENT
            return Verdict(
                VerdictSeverity.REFUSED,
                "PRICE_BELOW_RANGE",
                f"The price {last} is below the range's lower bound {params.lower}. "
                f"Starting now would buy about {opening_quote:.2f} of the base asset "
                f"at market, {share:.0f}% of the capital. Lower the range to "
                "include the price, or wait for it to return",
                numbers,
            )
        case RangePosition.ABOVE:
            return Verdict(
                VerdictSeverity.WARNING,
                "PRICE_ABOVE_RANGE",
                f"The price {last} is above the range's upper bound {params.upper}. "
                "The bot starts with nothing bought and places BUY orders only; it "
                "trades once the price falls into the range",
                numbers,
            )
        case RangePosition.INSIDE:
            return Verdict(
                VerdictSeverity.OK,
                "PRICE_IN_RANGE",
                "The price is inside the range",
                numbers,
            )
