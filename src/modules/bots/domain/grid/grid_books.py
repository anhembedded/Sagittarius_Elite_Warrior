"""`EPIC-029E`, `EPIC-039I` — what a fill does to a Grid's books: the inventory (or position),
its average cost, the realised figures and the completed cycles.

@details Pure functions over `GridRuntime`, split from `grid_reactions.py` (which decides what a
fact makes the ladder do) because they are the other abstraction level: arithmetic on money.

A runtime books **long** (Spot, LONG) or on a **signed position** (a SHORT grid, whose entries
are SELLs, or a NEUTRAL one, whose entries are both; `GridRuntime.entry_side`). Long is Spot's rule, unchanged: a BUY adds to the inventory (net of a
base fee) and to the cost, a SELL takes the average cost out and books the difference. The signed book
is its mirror on a position venue: a SELL deepens the (negative) inventory at its proceeds, a BUY
covers what is held and books `(average entry - price) x covered`; a fill past zero opens the other side. A position venue's fees are
paid in the quote asset, so the short book reads no base fee.

Plausible extension cases: a hedged pair of positions (two books behind the same two entry points).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
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


def book_exit_fill(
    runtime: GridRuntime, side: OrderSide, fill: LevelFill
) -> GridRuntime:
    """The runtime after a fill of an exit slice, which closes and never opens (`EPIC-039I`).

    A signed book (SHORT, NEUTRAL) books only the part that reduces the position it holds, so an
    exit sent for a position the runtime never counted (fills missed across a restart, then a halt
    that closes what the exchange holds) cannot leave a phantom position of the other sign. A
    Spot or LONG runtime is booked as `book_market_fill` always did: its sells already stop at
    what is held."""
    if runtime.entry_side is OrderSide.BUY:
        return book_inventory(runtime, side, fill)
    held = runtime.inventory
    if held == 0 or (held > 0) == (side is OrderSide.BUY):
        return runtime
    covered = min(fill.quantity, abs(held))
    share = covered / fill.quantity
    return book_inventory(
        runtime,
        side,
        replace(fill, quantity=covered, quote_fee=fill.quote_fee * share),
    )


def book_inventory(
    runtime: GridRuntime, side: OrderSide, fill: LevelFill
) -> GridRuntime:
    """The runtime after one fill of `side`, booked long or short as the runtime is."""
    if runtime.entry_side is not OrderSide.BUY:
        return _book_signed(runtime, side, fill)
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


@dataclass(frozen=True, slots=True)
class _Deal:
    """What one side of a fill trades: a price, a quantity and the quote fee that goes with it."""

    price: Decimal
    quantity: Decimal
    fee: Decimal


def _book_signed(runtime: GridRuntime, side: OrderSide, fill: LevelFill) -> GridRuntime:
    """A fill against a signed position (a SHORT or NEUTRAL grid, on a venue whose fees are all
    in the quote asset). A fill on the side of the position (or against none) deepens it at its
    price; a fill against it covers up to what is held and books `(price - average entry)` per
    unit covered (negated for a short), and what is left over opens the other side at its price
    (a position that is not a whole number of quantities, after a partial fill that ended)."""
    held = runtime.inventory
    sign = 1 if side is OrderSide.BUY else -1
    if held == 0 or (held > 0) == (sign > 0):
        return _deepen(runtime, side, _Deal(fill.price, fill.quantity, fill.quote_fee))
    covered = min(fill.quantity, abs(held))
    share = covered / fill.quantity
    average = runtime.average_cost or _ZERO
    direction = 1 if held > 0 else -1
    earned = (fill.price - average) * covered * direction - fill.quote_fee * share
    reduced = replace(
        runtime,
        inventory=held + sign * covered,
        cost=runtime.cost - average * covered,
        realised_total=runtime.realised_total + earned,
    )
    left = fill.quantity - covered
    if left == 0:
        return reduced
    return _deepen(reduced, side, _Deal(fill.price, left, fill.quote_fee * (1 - share)))


def _deepen(runtime: GridRuntime, side: OrderSide, deal: _Deal) -> GridRuntime:
    """The position grown by `deal`: a long adds its fee to its cost, a short takes it off its
    proceeds (so a fee always lowers the profit)."""
    worth = deal.price * deal.quantity
    if side is OrderSide.BUY:
        return replace(
            runtime,
            inventory=runtime.inventory + deal.quantity,
            cost=runtime.cost + worth + deal.fee,
        )
    return replace(
        runtime,
        inventory=runtime.inventory - deal.quantity,
        cost=runtime.cost + worth - deal.fee,
    )


def book_cycle(
    runtime: GridRuntime, completion: LevelOrder, price: Decimal
) -> GridRuntime:
    """Books the profit of the cycle `completion` closes, once. The entry's price is
    `paired_buy_price`: below the completing SELL of a long cycle, above the completing BUY of a
    short one (a NEUTRAL grid has both)."""
    if completion.paired_buy_price is None:
        return runtime
    quantity = completion.total_executed
    fee_quote = completion.quote_fee + completion.total_base_fee * price
    spread = completion.price - completion.paired_buy_price
    if completion.side is OrderSide.BUY:
        spread = -spread
    profit = spread * quantity - fee_quote - completion.paired_buy_fee_quote
    return replace(
        runtime,
        realised_profit=runtime.realised_profit + profit,
        completed_cycles=runtime.completed_cycles + 1,
    )
