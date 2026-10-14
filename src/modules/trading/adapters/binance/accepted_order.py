"""`BUG-205` — the order a venue accepted, not only the order that was sent.

A placement response names the quantity the exchange holds (`origQty`). The
clients used to hand back the order they sent, so everything above them — the
bot's saved ladder and the Orders panel — showed the sender's belief. This reads
the response's quantity and returns the order as accepted; a difference is logged
once, with both numbers. A response without a readable `origQty` leaves the order
as sent: the exchange has accepted it, so nothing here may raise.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from decimal import Decimal, InvalidOperation

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order

logger = logging.getLogger("App.Trading.OrderAcceptance")


def as_accepted(order: Order, response: object) -> Order:
    """`order` carrying the quantity `response` says the exchange accepted."""
    if order.quote_quantity is not None or not isinstance(response, dict):
        return order
    try:
        accepted = Decimal(str(response["origQty"]))
    except (KeyError, InvalidOperation):
        return order
    if accepted == order.quantity:
        return order
    logger.warning(
        "%s was sent for %s and accepted by the exchange for %s [order-quantity]",
        order.client_order_id,
        order.quantity,
        accepted,
    )
    return replace(order, quantity=accepted)
