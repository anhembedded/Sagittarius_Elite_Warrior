"""`EPIC-029E`, `EPIC-039I` — what a fill does to a Grid's books: the inventory (or position),
its average cost, the realised figures and the completed cycles.

@details Pure functions over `GridRuntime`, split from `grid_reactions.py` (which decides what a
fact makes the ladder do) because they are the other abstraction level: arithmetic on money.

A runtime books **long** (Spot, LONG) or **short** (a SHORT grid, whose entries are SELLs,
`GridRuntime.entry_side`). Long is Spot's rule, unchanged: a BUY adds to the inventory (net of a
base fee) and to the cost, a SELL takes the average cost out and books the difference. Short is
its mirror on a position venue: a SELL deepens the (negative) inventory at its proceeds, a BUY
covers what is held and books `(average entry - price) x covered`. A position venue's fees are
paid in the quote asset, so the short book reads no base fee.

Plausible extension cases: a NEUTRAL grid's position crosses zero (`EPIC-039I`, its own book
behind the same two entry points).
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridRuntime,
    LevelOrder,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide

if TYPE_CHECKING:
    from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_reactions import (
        LevelFill,
    )

_ZERO = Decimal(0)


def book_market_fill(
    runtime: GridRuntime, side: OrderSide, fill: LevelFill
) -> GridRuntime:
    """The inventory after a fill of one of the bot's market orders (the
    opening, an exit slice): no level holds it, and it owes no counter."""
    return book_inventory(runtime, side, fill)


def book_inventory(
    runtime: GridRuntime, side: OrderSide, fill: LevelFill
) -> GridRuntime:
    """The runtime after one fill of `side`, booked long or short as the runtime is."""
    if runtime.entry_side is OrderSide.SELL:
        return _book_short(runtime, side, fill)
    if side is OrderSide.BUY:
        return replace(
            runtime,
            inventory=runtime.inventory + fill.quantity - fill.base_fee,
            cost=runtime.cost + fill.price * fill.quantity + fill.quote_fee,
        )
    average = runtime.average_cost or _ZERO
    sold = min(fill.quantity + fill.base_fee, runtime.inventory)
    earned = fill.price * fill.quantity - fill.quote_fee - average * sold
    return replace(
        runtime,
        inventory=runtime.inventory - sold,
        cost=runtime.cost - average * sold,
        realised_total=runtime.realised_total + earned,
    )


def _book_short(runtime: GridRuntime, side: OrderSide, fill: LevelFill) -> GridRuntime:
    if side is OrderSide.SELL:
        return replace(
            runtime,
            inventory=runtime.inventory - fill.quantity,
            cost=runtime.cost + fill.price * fill.quantity - fill.quote_fee,
        )
    average = runtime.average_cost or _ZERO
    covered = min(fill.quantity, -runtime.inventory)
    earned = (average - fill.price) * covered - fill.quote_fee
    return replace(
        runtime,
        inventory=runtime.inventory + covered,
        cost=runtime.cost - average * covered,
        realised_total=runtime.realised_total + earned,
    )


def book_cycle(
    runtime: GridRuntime, completion: LevelOrder, price: Decimal
) -> GridRuntime:
    """Books the profit of the cycle `completion` closes, once. The entry's price is
    `paired_buy_price`: below the completing SELL of a long grid, above the completing BUY of a
    short one."""
    if completion.paired_buy_price is None:
        return runtime
    quantity = completion.total_executed
    fee_quote = completion.quote_fee + completion.total_base_fee * price
    spread = completion.price - completion.paired_buy_price
    if runtime.entry_side is OrderSide.SELL:
        spread = -spread
    profit = spread * quantity - fee_quote - completion.paired_buy_fee_quote
    return replace(
        runtime,
        realised_profit=runtime.realised_profit + profit,
        completed_cycles=runtime.completed_cycles + 1,
    )
