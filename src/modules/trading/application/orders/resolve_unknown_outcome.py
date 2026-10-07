"""`BUG-170` — settle an order whose submission got no readable answer.

`resolve_unknown` asks the exchange for the order by the client order id sent:
found, it was placed (the order is returned); absent, `OrderNotPlacedError`;
the read itself unreadable, `OrderOutcomeUnknownError` again, which the caller
must treat as "may be live", never as "not placed". Every caller of
`ITradingClient.place_order` that can send a live order uses it, through
`place_resolving_unknown` or, when it counts the order first, directly.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_client import (
    ITradingClient,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_outcome_unknown import (
    OrderNotPlacedError,
    OrderOutcomeUnknownError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_rejection_reason import (
    OrderRejectedByExchangeError,
)

logger = logging.getLogger("App.CommandHandler")


def place_resolving_unknown(client: ITradingClient, order: Order) -> Order:
    """`place_order`, with an unreadable answer resolved by `resolve_unknown`."""
    try:
        return client.place_order(order)
    except OrderOutcomeUnknownError as unknown:
        return resolve_unknown(client, unknown)


def resolve_unknown(client: ITradingClient, unknown: OrderOutcomeUnknownError) -> Order:
    """@return The order the exchange holds: it was placed.
    @raise OrderNotPlacedError The exchange holds no such order.
    @raise OrderOutcomeUnknownError It could not be asked either.
    """
    try:
        found = client.find_order(unknown.symbol, unknown.client_order_id)
    except (OrderOutcomeUnknownError, OrderRejectedByExchangeError) as unread:
        reason = (
            unread.reason
            if isinstance(unread, OrderOutcomeUnknownError)
            else unread.raw_message
        )
        logger.error(
            "Order %s on %s: outcome still unknown after asking the exchange: %s [order-outcome-unknown]",
            unknown.client_order_id,
            unknown.symbol,
            reason,
        )
        raise OrderOutcomeUnknownError(
            unknown.symbol, unknown.client_order_id, f"{unknown.reason}; {reason}"
        ) from unread
    if found is None:
        logger.warning(
            "Order %s on %s: the exchange holds no such order, not placed [order-not-placed]",
            unknown.client_order_id,
            unknown.symbol,
        )
        raise OrderNotPlacedError(
            unknown.symbol, unknown.client_order_id, unknown.reason
        ) from unknown
    logger.warning(
        "Order %s on %s: the submission's answer was unreadable, the exchange holds it as %s [order-confirmed]",
        unknown.client_order_id,
        unknown.symbol,
        found.status.name,
    )
    return found
