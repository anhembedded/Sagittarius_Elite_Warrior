"""`EPIC-035S` (audit L3) — levels that round to one price are refused.

Rounding to the venue's tick can merge neighbouring levels (a step finer than a
tick). The ladder then holds two rungs at one price, and `GridRuntime.level_at`
answers the first of them for either, so a fill or an adopted order can be
booked on the wrong rung. The fee break-even warning notices a thin step only
indirectly; this names the collision.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_check_inputs import (
    GridCheckInputs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import (
    Verdict,
    VerdictSeverity,
)

#: How many colliding groups the sentence names before it counts the rest.
_NAMED_GROUPS = 3


def check_distinct_levels(inputs: GridCheckInputs) -> Verdict:
    by_price: dict[Decimal, list[int]] = defaultdict(list)
    for level in inputs.plan.levels:
        by_price[level.price].append(level.index)
    colliding = {price: at for price, at in by_price.items() if len(at) > 1}
    numbers = {
        "levels": Decimal(len(inputs.plan.levels)),
        "colliding_prices": Decimal(len(colliding)),
        "tick_size": inputs.terms.tick_size,
    }
    if not colliding:
        return Verdict(
            VerdictSeverity.OK,
            "LEVELS_DISTINCT",
            "Every level has its own price",
            numbers,
        )
    named = ", ".join(
        f"levels {_joined(at)} at {price:f}"
        for price, at in list(colliding.items())[:_NAMED_GROUPS]
    )
    more = len(colliding) - _NAMED_GROUPS
    return Verdict(
        VerdictSeverity.REFUSED,
        "LEVELS_ROUND_TO_ONE_PRICE",
        f"The exchange's price step {inputs.terms.tick_size:f} puts several levels "
        f"on one price: {named}{f' and {more} more' if more > 0 else ''}. Use "
        "fewer grids or a wider range",
        numbers,
    )


def _joined(indexes: list[int]) -> str:
    *head, last = indexes
    return f"{', '.join(map(str, head))} and {last}"
