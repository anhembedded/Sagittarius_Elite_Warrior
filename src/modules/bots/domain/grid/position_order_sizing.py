"""`EPIC-039I` - the orders a position venue's ladder can send, and whether the exchange takes them.

@details One sizing for the Plan's checks and for the executor (`BUG-212`: a check passed while the
executor sent an order below the minimum, because each had counted the orders its own way). A
position ladder gives every order one quantity (`LevelSizing.EQUAL_QUANTITY`), and **any level can
hold an order sooner or later**: a fill at one rung owes its counter at the neighbouring rung, so
the level left EMPTY at start, or one a SELL leaves, takes an order too. The orders the bot may
send are therefore the plan's one quantity at *every* level's price, not only at the levels that
hold an order at the start.

Counters are not sized again: a completion is the quantity its entry executed and a re-entry is the
level's `buy_quantity`, which `runtime_from_plan` sets to the plan's one quantity. A partial
remainder under the minimum is settled for what it executed (`grid_reactions._settle_short`), so it
is never sent.

`first_breach` is the decision; the plan's `check_min_notional` and `check_max_notional` read the
same `smallest_order` and `largest_order`, and `PositionOpening` calls `first_breach` before it
sends anything. `test_position_orders_the_reactions_send.py` fills a ladder through the real
reactions and holds every order they emit to the filters.

Plausible extension cases: a `minQty` filter (one more `BreachKind` and one more test in
`first_breach`); a per-level price-band check (the same loop over `sized_orders`).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    ExchangeTerms,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import (
    GridPlan,
    LevelSizing,
)


class BreachKind(str, Enum):
    """Which filter an order breaks."""

    #: The quantity rounds to nothing at the exchange's step: no order can be sent at all.
    ROUNDS_TO_NOTHING = "rounds_to_nothing"
    BELOW_MINIMUM = "below_minimum"
    ABOVE_CAP = "above_cap"


@dataclass(frozen=True, slots=True)
class SizedOrder:
    """One order the ladder may send: a rung's price and the plan's one quantity."""

    level_index: int
    price: Decimal
    quantity: Decimal

    @property
    def notional(self) -> Decimal:
        return self.price * self.quantity


@dataclass(frozen=True, slots=True)
class OrderBreach:
    kind: BreachKind
    order: SizedOrder

    def describe(self, terms: ExchangeTerms) -> str:
        """The refusal in words, naming the order, its worth and the filter."""
        order = self.order
        if self.kind is BreachKind.ROUNDS_TO_NOTHING:
            return (
                "an order of the ladder rounds to nothing at the exchange's quantity step "
                f"{terms.step_size}; raise the capital or use fewer grids"
            )
        which = (
            f"below the exchange minimum of {terms.min_notional}"
            if self.kind is BreachKind.BELOW_MINIMUM
            else f"above trading's cap of {terms.max_notional_per_order} per order"
        )
        return (
            f"the order at level {order.level_index} ({order.quantity} at {order.price}) "
            f"is worth {order.notional:.2f}, {which}"
        )


def sized_orders(plan: GridPlan) -> tuple[SizedOrder, ...]:
    """Every order the ladder may send. A position ladder (`LevelSizing.EQUAL_QUANTITY`): the
    plan's one quantity at each level's price. An equal-capital plan has no such guarantee (its
    quantities differ by price and its buys pay fee in base), so only the orders it lays are known:
    its levels that hold one."""
    if plan.level_sizing is LevelSizing.EQUAL_QUANTITY:
        quantity = plan.uniform_quantity or Decimal(0)
        return tuple(SizedOrder(lv.index, lv.price, quantity) for lv in plan.levels)
    return tuple(
        SizedOrder(lv.index, lv.price, lv.quantity) for lv in plan.order_levels
    )


def smallest_order(plan: GridPlan) -> SizedOrder:
    return min(
        sized_orders(plan), key=lambda order: (order.notional, order.level_index)
    )


def largest_order(plan: GridPlan) -> SizedOrder:
    return max(
        sized_orders(plan), key=lambda order: (order.notional, -order.level_index)
    )


def first_breach(plan: GridPlan, terms: ExchangeTerms) -> OrderBreach | None:
    """The first filter the ladder's orders break, or `None`: the minimum is judged on the
    smallest order, the cap on the largest."""
    smallest, largest = smallest_order(plan), largest_order(plan)
    if smallest.quantity <= 0:
        return OrderBreach(BreachKind.ROUNDS_TO_NOTHING, smallest)
    if smallest.notional < terms.min_notional:
        return OrderBreach(BreachKind.BELOW_MINIMUM, smallest)
    if largest.notional > terms.max_notional_per_order:
        return OrderBreach(BreachKind.ABOVE_CAP, largest)
    return None
