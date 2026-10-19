"""`BOT-189` — an order of the ladder that filled whole, as the owner is told of it.

A fact `on_fill` hands back beside the runtime (`Reaction.filled`), so the executor can announce
it from the one place a fill is settled. It copies the numbers at that moment: the cycle's profit
is the difference `book_cycle` made, and the run totals are the ones right after it, so a second
fill settled in the same reaction (a parked counter replayed) does not see the first one's.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridRuntime,
    LevelOrder,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide


@dataclass(frozen=True, slots=True)
class FilledOrder:
    """One order that executed in full."""

    client_order_id: str
    level_index: int
    side: OrderSide
    #: The order's own price (a limit order fills at it or better).
    price: Decimal
    #: Everything the level's order executed, an earlier re-placed order's part included.
    quantity: Decimal
    #: The net profit `book_cycle` booked for the cycle this fill closed; `None` when it closed none.
    cycle_profit: Decimal | None
    #: The run's realized profit and closed cycles right after this fill.
    realised_total: Decimal
    completed_cycles: int


def filled_order(
    level_index: int,
    order: LevelOrder,
    before: GridRuntime,
    after: GridRuntime,
) -> FilledOrder:
    """`order` filled whole; `before` and `after` are the runtime around its cycle booking."""
    closed = after.completed_cycles > before.completed_cycles
    return FilledOrder(
        client_order_id=order.client_order_id,
        level_index=level_index,
        side=order.side,
        price=order.price,
        quantity=order.total_executed,
        cycle_profit=after.realised_profit - before.realised_profit if closed else None,
        realised_total=after.realised_profit,
        completed_cycles=after.completed_cycles,
    )
