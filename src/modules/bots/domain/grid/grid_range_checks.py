"""`EPIC-035L` (audit H7), superseded by `EPIC-044`, ADR 044 D6 - the price outside the range, told.

A Grid started while the price is outside its range starts and waits: it places nothing until the
price is inside, then lays its ladder as a normal start would (the owner's decision of 2026-10-21).
So `PRICE_BELOW_RANGE` and `PRICE_ABOVE_RANGE` no longer refuse or warn: they say, for every
direction alike, that the bot will wait and for what. The words were once the LONG ladder's
(`would buy ... at market`, `BUY orders only`) and were false for a SHORT, whose opening trade is
the mirror; they now describe no trade at all.

The price judged is the market's own (`inputs.market`): the plan the other checks read is made at
the nearest bound (`evaluate_grid`), which is where the bot will enter, so `plan.last_price` is not
where the price is. D2 holds: nothing here mentions a stop loss.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_advice import plain
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_check_inputs import (
    GridCheckInputs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_entry_gate import (
    better_is_lower,
    trigger_met,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.range_position import (
    RangePosition,
    range_position,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import (
    Verdict,
    VerdictSeverity,
)

_CODES = {
    RangePosition.BELOW: "PRICE_BELOW_RANGE",
    RangePosition.ABOVE: "PRICE_ABOVE_RANGE",
}


def check_price_against_range(inputs: GridCheckInputs) -> Verdict:
    params = inputs.params
    price = inputs.market.last_price
    position = range_position(price, params.lower, params.upper)
    numbers = {"last_price": price, "lower": params.lower, "upper": params.upper}
    trigger = params.trigger_price
    if (
        position is RangePosition.INSIDE
        and trigger is not None
        and not trigger_met(params, price)
    ):
        return _trigger_unmet(params, trigger, numbers)
    if position is RangePosition.INSIDE:
        return Verdict(
            VerdictSeverity.OK,
            "PRICE_IN_RANGE",
            "The price is inside the range",
            numbers,
        )
    edge = params.lower if position is RangePosition.BELOW else params.upper
    return Verdict(
        VerdictSeverity.OK,
        _CODES[position],
        f"Starts waiting for the price to enter {plain(params.lower)}-"
        f"{plain(params.upper)} (now {plain(price)}); nothing is placed until it does",
        {**numbers, "entry_edge": edge},
    )


def _trigger_unmet(
    params: GridParams, trigger: Decimal, numbers: dict[str, Decimal]
) -> Verdict:
    """The price is in the range but not yet at the trigger: the bot waits, like a limit order
    (`EPIC-046A`, ADR 046 D5)."""
    side = "at or below" if better_is_lower(params) else "at or above"
    return Verdict(
        VerdictSeverity.OK,
        "TRIGGER_NOT_MET",
        f"Starts waiting for the price {side} the trigger {plain(trigger)} "
        f"(now {plain(numbers['last_price'])}); nothing is placed until it is",
        {**numbers, "trigger_price": trigger},
    )
