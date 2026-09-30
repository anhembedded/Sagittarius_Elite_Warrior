"""`EPIC-028E` — `GetOpenOrdersQueryHandler`.

@details Reads through the venue's own `ITradingClient.get_open_orders`, the
call `EnableTradingCommandHandler` already reconciles against, from a client
built `VALIDATE_ONLY` (irrelevant for a read, the same reasoning
`GetOpenPositionsQueryHandler` gives).
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_open_orders.query import (
    GetOpenOrdersQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_submission_mode import (
    OrderSubmissionMode,
)

logger = logging.getLogger("App.QueryHandler")


class GetOpenOrdersQueryHandler(IQueryHandler[GetOpenOrdersQuery, tuple[Order, ...]]):
    def __init__(self, contexts: IVenueContexts) -> None:
        self._contexts = contexts

    def execute(self, query: GetOpenOrdersQuery) -> tuple[Order, ...]:
        logger.debug(
            "Handling GetOpenOrdersQuery on %s (%s)",
            query.venue.value,
            query.symbol or "every symbol",
        )
        client = self._contexts.get(query.venue).client_factory.create(
            OrderSubmissionMode.VALIDATE_ONLY
        )
        return tuple(client.get_open_orders(query.symbol))
