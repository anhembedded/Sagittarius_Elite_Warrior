"""`EPIC-046A` - whether a price lets a Grid start laying its ladder (ADR 046 D1, D2).

One definition for every place that asks: the start (`GridRangeEntry.waits_for_the_range`), the
flat resume, the waiting bot's price watch and the Plan's entry price (`entry_plan`). The gate is
the range (`range_position`, the bounds included) and then the optional **trigger price**, which
works like a limit order on the entry:

  * a LONG grid enters when the price is **at or below** the trigger (a better, lower buy);
  * a SHORT grid enters when the price is **at or above** it (a better, higher sell);
  * no trigger: the range alone, exactly as `EPIC-044`.

The trigger is a condition on the entry only. A bot that has laid its ladder never asks again, as
a filled limit order does not unfill (ADR 046 D3).
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.trade_direction import (
    TradeDirection,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.range_position import (
    RangePosition,
    range_position,
)


class EntryGate(str, Enum):
    """What stands between a price and the ladder."""

    OPEN = "OPEN"
    OUTSIDE_RANGE = "OUTSIDE_RANGE"
    TRIGGER_NOT_MET = "TRIGGER_NOT_MET"


def entry_gate(params: GridParams, price: Decimal) -> EntryGate:
    """The range is judged first: a price outside it is never an entry, trigger or not."""
    if range_position(price, params.lower, params.upper) is not RangePosition.INSIDE:
        return EntryGate.OUTSIDE_RANGE
    if not trigger_met(params, price):
        return EntryGate.TRIGGER_NOT_MET
    return EntryGate.OPEN


def trigger_met(params: GridParams, price: Decimal) -> bool:
    """`True` when `params` has no trigger, or `price` is at the trigger or better for its side."""
    trigger = params.trigger_price
    if trigger is None:
        return True
    if params.direction is TradeDirection.SHORT:
        return price >= trigger
    return price <= trigger


def entry_price(params: GridParams, price: Decimal) -> Decimal:
    """Where the bot will enter if it enters from `price`: the price pulled into the range and,
    while the trigger is unmet, to the trigger. The Plan draws its ladder there (ADR 046 D5)."""
    inside = min(max(price, params.lower), params.upper)
    if trigger_met(params, inside):
        return inside
    return params.trigger_price if params.trigger_price is not None else inside
