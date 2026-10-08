"""`EPIC-035L` — where a price stands against a Grid's range.

One definition for the two places that ask: the Start check (`grid_range_checks.py`)
and the running bot's range watch. The bounds themselves are *inside* the range:
a price exactly on the lower or the upper bound is not an exit, because the plan
classes a level as BUY or SELL by its price strictly below or above the last
price (`grid_plan.py`), so a price on a bound still leaves that level's order.
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum


class RangePosition(str, Enum):
    """Below the lower bound, inside the range (bounds included), above the upper bound."""

    BELOW = "BELOW"
    INSIDE = "INSIDE"
    ABOVE = "ABOVE"


def range_position(price: Decimal, lower: Decimal, upper: Decimal) -> RangePosition:
    if price < lower:
        return RangePosition.BELOW
    if price > upper:
        return RangePosition.ABOVE
    return RangePosition.INSIDE
