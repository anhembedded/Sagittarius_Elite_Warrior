"""`EPIC-039K` — the resting orders of a position grid, as the replay moves them.

@details The rules are `grid_position_model.py`'s (`EPIC-039B`): a filled level becomes empty
and its counter goes one level up after a BUY and one down after a SELL, with the quantity just
filled (`place_counter`, shared, not copied). The fill test is the Spot replay's
(`grid_fill_rule.buy_fills` / `sell_fills`: a level fills only when the price traded a tick
through it) and so is the timing: a counter placed during a step rests from the next one, so a
single 1-second kline never completes a round trip.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_fill_rule import (
    buy_fills,
    sell_fills,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_overlay import (
    LevelState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import (
    GridPlan,
    LevelSide,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_position_model import (
    place_counter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide


class Ladder:
    """The levels of a plan: who rests where, and with what quantity."""

    def __init__(self, plan: GridPlan, tick_size: Decimal) -> None:
        self._prices = [level.price for level in plan.levels]
        self._sides = [level.side for level in plan.levels]
        self._quantities = [level.quantity for level in plan.levels]
        self._tick = tick_size
        self._placed_this_step: set[int] = set()

    def start_step(self) -> None:
        """A new step begins: what was placed in the last one rests now."""
        self._placed_this_step.clear()

    def reaches(self, low: Decimal, high: Decimal) -> bool:
        """Whether a range `low`-`high`, the next step's, would fill a resting order. The
        orders placed in the step that just ended count: they rest from this one."""
        return bool(self._buys_reached(low) or self._sells_reached(high))

    def next_buy(self, low: Decimal) -> int | None:
        """The highest BUY a fall to `low` fills in this step, if any."""
        reached = [
            i for i in self._buys_reached(low) if i not in self._placed_this_step
        ]
        return max(reached, key=lambda index: self._prices[index], default=None)

    def next_sell(self, high: Decimal) -> int | None:
        """The lowest SELL a rise to `high` fills in this step, if any."""
        reached = [
            i for i in self._sells_reached(high) if i not in self._placed_this_step
        ]
        return min(reached, key=lambda index: self._prices[index], default=None)

    def _buys_reached(self, low: Decimal) -> list[int]:
        return [
            index
            for index, side in enumerate(self._sides)
            if side is LevelSide.BUY and buy_fills(self._prices[index], low, self._tick)
        ]

    def _sells_reached(self, high: Decimal) -> list[int]:
        return [
            index
            for index, side in enumerate(self._sides)
            if side is LevelSide.SELL
            and sell_fills(self._prices[index], high, self._tick)
        ]

    def price_of(self, index: int) -> Decimal:
        return self._prices[index]

    def fill(self, index: int) -> tuple[OrderSide, Decimal]:
        """Fill level `index`: its side and quantity, the counter placed."""
        side = OrderSide.BUY if self._sides[index] is LevelSide.BUY else OrderSide.SELL
        quantity = self._quantities[index]
        self._sides[index] = LevelSide.EMPTY
        target = index + 1 if side is OrderSide.BUY else index - 1
        was_empty = 0 <= target < len(self._sides) and (
            self._sides[target] is LevelSide.EMPTY
        )
        place_counter(self._sides, self._quantities, index, side, quantity)
        if was_empty and self._sides[target] is not LevelSide.EMPTY:
            self._placed_this_step.add(target)
        return side, quantity

    def cancel_all(self) -> None:
        """Every resting order cancelled: an exit or a liquidation ended the run."""
        self._sides = [LevelSide.EMPTY] * len(self._sides)

    def drawn(self) -> tuple[tuple[int, LevelState], ...]:
        """Each level as the chart draws it."""
        return tuple((index, _drawn(side)) for index, side in enumerate(self._sides))


def _drawn(side: LevelSide) -> LevelState:
    if side is LevelSide.BUY:
        return LevelState.RESTING_BUY
    if side is LevelSide.SELL:
        return LevelState.RESTING_SELL
    return LevelState.EMPTY
