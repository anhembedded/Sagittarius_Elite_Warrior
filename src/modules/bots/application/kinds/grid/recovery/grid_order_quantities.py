"""`BUG-205` — a saved order's quantity is the exchange's, not the bot's belief.

The reconcile matched a saved order to the exchange's open orders by id alone, so
an order the exchange holds at another quantity than the bot saved stayed shown
(the Orders panel) and booked (a fill's completeness, the counter order's size)
at the saved one. The exchange's record is the truth (`domain-truth-rule.md`): a
resting order is adopted at the quantity the exchange lists, and each change is
named. Nothing is halted: the order rests and trades as the exchange holds it,
and the inventory check that follows still compares the bot's account with the
exchange's own derivation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridRuntime,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_record import (
    OrderRecord,
)

logger = logging.getLogger("App.Bots.GridExecutor")


@dataclass(frozen=True, slots=True)
class QuantityExceedsSaved:
    """The exchange holds an order for more than the bot saved: the bot's books
    do not cover what the order can trade, so the reconcile halts on it."""

    client_order_id: str
    level_index: int
    saved: Decimal
    exchange: Decimal

    @property
    def detail(self) -> str:
        return (
            f"L{self.level_index} {self.client_order_id} is held by the exchange for "
            f"{self.exchange}, more than the {self.saved} the bot saved"
        )


def adopt_exchange_quantities(
    bot_id: str,
    runtime: GridRuntime,
    open_orders: tuple[Order, ...],
    records: dict[str, OrderRecord],
) -> GridRuntime | QuantityExceedsSaved:
    """`runtime` with every saved order carrying the quantity the exchange holds
    for it: the open-order list's for an order still resting, history's for one
    that is gone (a fill the app missed settles against the quantity the order
    really had). A smaller quantity is adopted and logged; a larger one is
    returned, never adopted, for the reconcile to halt on."""
    held = {str(o.client_order_id): o.quantity for o in open_orders}
    held |= {
        cid: record.order.quantity for cid, record in records.items() if cid not in held
    }
    for level in runtime.levels:
        saved = level.order
        quantity = held.get(str(saved.client_order_id)) if saved else None
        if saved is None or quantity is None or quantity == saved.quantity:
            continue
        if quantity > saved.quantity:
            return QuantityExceedsSaved(
                saved.client_order_id, level.index, saved.quantity, quantity
            )
        logger.warning(
            "Bot %s: %s at L%d is held by the exchange for %s, the ladder had %s; "
            "the exchange's quantity is adopted [order-quantity]",
            bot_id,
            saved.client_order_id,
            level.index,
            quantity,
            saved.quantity,
        )
        runtime = runtime.with_level(
            replace(level, order=replace(saved, quantity=quantity))
        )
    return runtime
