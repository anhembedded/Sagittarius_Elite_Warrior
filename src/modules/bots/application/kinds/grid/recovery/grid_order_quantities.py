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
from dataclasses import replace
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridRuntime,
    LevelOrder,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order

logger = logging.getLogger("App.Bots.GridExecutor")


def adopt_exchange_quantities(
    bot_id: str, runtime: GridRuntime, open_orders: tuple[Order, ...]
) -> GridRuntime:
    """`runtime` with every saved order the exchange lists at another quantity
    carrying the exchange's; each change is logged."""
    listed = {str(order.client_order_id): order.quantity for order in open_orders}
    for level in runtime.levels:
        saved = level.order
        quantity = listed.get(str(saved.client_order_id)) if saved else None
        if saved is None or quantity is None or quantity == saved.quantity:
            continue
        logger.warning(
            "Bot %s: %s at L%d rests at %s on the exchange, the ladder had %s; "
            "the exchange's quantity is adopted [order-quantity]",
            bot_id,
            saved.client_order_id,
            level.index,
            quantity,
            saved.quantity,
        )
        runtime = runtime.with_level(replace(level, order=_resized(saved, quantity)))
    return runtime


def _resized(order: LevelOrder, quantity: Decimal) -> LevelOrder:
    return replace(order, quantity=quantity)
