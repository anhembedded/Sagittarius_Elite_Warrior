"""`EPIC-039D` — how far a Futures owner's position could reach, and whether
an order lets it reach further than its budget allows.

@details Worst case, in One-way mode with the owner's orders filling in the
order least kind to it: every open BUY and none of the SELLs (long case), or
every open SELL and none of the BUYs (short case). Each case is **valued** as
the part of the held position that survives, at its average entry, plus what
the orders that add to it commit **at their own prices** (a flip's excess is
valued at the average price of the orders that cause it). So the verdict does
not depend on the order a ladder is sent in, and a ladder's total is what
`capital × leverage` (DECISION O2) bounds.

An order is refused for exposure only when it is **the one that raises** the
worst case above the ceiling. One that leaves the worst case where it was (a
reduce-only exit, a sell that only closes) passes even when the owner is
already over, so a position can always be reduced.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    FuturesLimits,
    OwnerBudgetFacts,
    PositionExposure,
)

_ZERO = Decimal(0)


def notional_within_limits(facts: OwnerBudgetFacts, order_notional: Decimal) -> bool:
    """@brief Whether the worst-case position, with this order, is worth no
    more than `max_position_notional`, or is no worse than without it."""
    return _within(facts, order_notional, _limits_of(facts).max_position_notional)


def margin_within_limits(facts: OwnerBudgetFacts, order_notional: Decimal) -> bool:
    """@brief Whether the initial margin of the worst-case position, with
    this order, is at most `committed_margin`, or is no worse than without it."""
    limits = _limits_of(facts)
    return _within(facts, order_notional, limits.committed_margin * limits.leverage)


def worst_case_value(
    exposure: PositionExposure, added: tuple[Decimal, Decimal, Decimal, Decimal]
) -> Decimal:
    """@brief The worst of the long and the short case, valued as the module
    docstring says. `added` is `(buy quantity, buy notional, sell quantity,
    sell notional)` of the orders to count on top of the held position."""
    buy_quantity, buy_notional, sell_quantity, sell_notional = added
    held = exposure.position.quantity
    entry = exposure.position.average_entry or _ZERO
    return max(
        _case_value(held, entry, buy_quantity, buy_notional),
        _case_value(-held, entry, sell_quantity, sell_notional),
    )


def _case_value(
    held: Decimal, entry: Decimal, added_quantity: Decimal, added_notional: Decimal
) -> Decimal:
    """The value of `held` (signed towards the case's direction) once
    `added_quantity` more is added in that direction at `added_notional`."""
    if held >= 0:
        return held * entry + added_notional
    closed = min(-held, added_quantity)
    excess = added_quantity - closed
    flipped = added_notional * excess / added_quantity if added_quantity > 0 else _ZERO
    return (-held - closed) * entry + flipped


def _within(
    facts: OwnerBudgetFacts, order_notional: Decimal, notional_ceiling: Decimal
) -> bool:
    exposure = facts.position
    if exposure is None:
        raise ValueError("an exposure check needs a Futures owner's position")
    before = (
        exposure.open_adding_buy_quantity,
        exposure.open_adding_buy_notional,
        exposure.open_adding_sell_quantity,
        exposure.open_adding_sell_notional,
    )
    buying = facts.order_side is OrderSide.BUY and not exposure.order_reduce_only
    selling = facts.order_side is OrderSide.SELL and not exposure.order_reduce_only
    after = (
        before[0] + (facts.order_quantity if buying else _ZERO),
        before[1] + (order_notional if buying else _ZERO),
        before[2] + (facts.order_quantity if selling else _ZERO),
        before[3] + (order_notional if selling else _ZERO),
    )
    value_after = worst_case_value(exposure, after)
    return value_after <= notional_ceiling or value_after <= worst_case_value(
        exposure, before
    )


def _limits_of(facts: OwnerBudgetFacts) -> FuturesLimits:
    limits = facts.budget.futures
    if limits is None:
        raise ValueError("an exposure check needs a Futures owner's limits")
    return limits
