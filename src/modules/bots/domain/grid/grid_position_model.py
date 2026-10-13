"""`EPIC-039B` - a MODEL of a position grid's signed position along a price path (DESIGN §5).

**This is a model, not a replay of live behaviour.** It applies the fill rule below to a plan;
it does not run the executor. Once the Futures executor exists (`EPIC-039H`), a Futures
backtest must either replay that executor, as `grid_replay.py` does for Spot, or be backed by a
test that checks this model against the executor on the same fills (`futures_replay.py` says the
same, `EPIC-039K`).

`model_position_along` is the small, pure model a position venue's Grid rests on: it moves a price
along a path, fills the plan's resting orders the way the live ladder does, and keeps the
signed position and the profit that closing it earned. It is not the Spot replay
(`grid_replay.py` runs the live executor's own reactions, base fees and paired buy prices, and
stays the Spot oracle); it is the model that `futures_replay.py` (`EPIC-039K`) extends with costs, funding and liquidation,
and that `EPIC-039F`'s liquidation estimate reads the position range from.

@par The fill rule
A BUY fills when the price reaches it from above (`price <= level`), a SELL when it reaches it
from below (`price >= level`). The filled level becomes EMPTY and its **counter** goes to the
next level (up after a BUY, down after a SELL) with the quantity just filled. A counter that
has nowhere to go (past the range edge) is not placed.

**This is not the live Spot ladder's counter rule.** The live ladder (`grid_reactions.py`)
sizes the counter BUY by its own level's buy quantity and nets the counter SELL of the base
fee; the model gives every counter the quantity just filled. The two agree only when every
level has the same quantity and no fee is paid in base, which is `LevelSizing.EQUAL_QUANTITY`
on a position venue. So the model refuses a plan sized any other way: read a Spot-shaped
position off it and it would show no drift where the live ladder has some
(`test_grid_equal_capital_drift.py` runs that drift on the real replay).

@par What it shows
With the same quantity `q` at every level (`LevelSizing.EQUAL_QUANTITY`) the position after a
fill at level `i` is `q * (N - i - c)`: it depends on where the fill was and on the direction
alone, never on the way the price took. `test_grid_position_model.py` shows it on random paths
for LONG, SHORT and NEUTRAL.

@par Profit
The position is carried at an average entry price. A fill that shrinks it realises
`closed * (price - entry)` for a long and `closed * (entry - price)` for a short; one that
crosses zero closes the old side and opens the new at the fill price. The opening trade is
priced at the plan's last price. No fees, funding or liquidation: `futures_replay.py` (`EPIC-039K`) books
its fills with this module's `PositionBook` and adds them.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import (
    GridPlan,
    LevelSide,
    LevelSizing,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide

_ZERO = Decimal(0)


@dataclass(frozen=True, slots=True)
class PositionFill:
    """One fill of the model and the position it left."""

    level_index: int
    side: OrderSide
    price: Decimal
    quantity: Decimal
    position_after: Decimal


@dataclass(frozen=True, slots=True)
class PositionModelRun:
    """Everything a path did to the ladder."""

    opening_position: Decimal
    fills: tuple[PositionFill, ...]
    position: Decimal
    #: Profit booked by the fills that shrank the position (no fees).
    realised: Decimal
    #: The average entry price of what is held, `None` when flat.
    entry_price: Decimal | None


@dataclass(slots=True)
class PositionBook:
    """The signed position and its average entry, advanced fill by fill.

    @details Public since `EPIC-039K`: the Futures replay (`futures_replay.py`) books its
    fills with this very class, so the model and the replay cannot disagree on what a fill
    does to the position and its profit."""

    position: Decimal
    entry: Decimal
    realised: Decimal = _ZERO

    def fill(self, side: OrderSide, quantity: Decimal, price: Decimal) -> None:
        signed = quantity if side is OrderSide.BUY else -quantity
        held = self.position
        if held == 0 or (held > 0) == (signed > 0):
            total = abs(held) + quantity
            self.entry = (abs(held) * self.entry + quantity * price) / total
            self.position = held + signed
            return
        closed = min(abs(held), quantity)
        direction = 1 if held > 0 else -1
        self.realised += closed * (price - self.entry) * direction
        self.position = held + signed
        if abs(signed) > abs(held):
            self.entry = price
        elif self.position == 0:
            self.entry = _ZERO


def model_position_along(plan: GridPlan, path: Sequence[Decimal]) -> PositionModelRun:
    """The ladder of `plan` modelled along `path`, a price after price.

    @raise ValueError `plan` was not sized with `LevelSizing.EQUAL_QUANTITY`.
    """
    if plan.level_sizing is not LevelSizing.EQUAL_QUANTITY:
        raise ValueError(
            "the position model reads only a plan sized with LevelSizing.EQUAL_QUANTITY"
        )
    sides = [level.side for level in plan.levels]
    quantities = [level.quantity for level in plan.levels]
    prices = [level.price for level in plan.levels]
    book = PositionBook(plan.opening_quantity, plan.last_price)
    fills: list[PositionFill] = []
    for point in path:
        while (index := _next_fill(sides, prices, point)) is not None:
            side = OrderSide.BUY if sides[index] is LevelSide.BUY else OrderSide.SELL
            quantity = quantities[index]
            book.fill(side, quantity, prices[index])
            fills.append(
                PositionFill(index, side, prices[index], quantity, book.position)
            )
            sides[index] = LevelSide.EMPTY
            place_counter(sides, quantities, index, side, quantity)
    return PositionModelRun(
        plan.opening_quantity,
        tuple(fills),
        book.position,
        book.realised,
        None if book.position == 0 else book.entry,
    )


def _next_fill(
    sides: list[LevelSide], prices: list[Decimal], point: Decimal
) -> int | None:
    """The next resting order the price passes on its way to `point`, if any.

    A fall passes the BUYs from the highest down; a rise passes the SELLs from the lowest
    up. Both cannot be reached at one point: every BUY rests below every SELL.
    """
    buys = [
        index
        for index, side in enumerate(sides)
        if side is LevelSide.BUY and point <= prices[index]
    ]
    if buys:
        return max(buys, key=lambda index: prices[index])
    sells = [
        index
        for index, side in enumerate(sides)
        if side is LevelSide.SELL and point >= prices[index]
    ]
    return min(sells, key=lambda index: prices[index]) if sells else None


def place_counter(
    sides: list[LevelSide],
    quantities: list[Decimal],
    index: int,
    filled: OrderSide,
    quantity: Decimal,
) -> None:
    """The counter of a fill: up after a BUY, down after a SELL, the same quantity."""
    target = index + 1 if filled is OrderSide.BUY else index - 1
    if not 0 <= target < len(sides) or sides[target] is not LevelSide.EMPTY:
        return
    sides[target] = LevelSide.SELL if filled is OrderSide.BUY else LevelSide.BUY
    quantities[target] = quantity
