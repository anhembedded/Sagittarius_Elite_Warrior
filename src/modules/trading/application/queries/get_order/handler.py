"""`EPIC-039L` — `GetOrderQueryHandler`.

@details Reads one order through the venue's own `ITradingClient.find_order`, the call that
resolves an unknown outcome: a regular order by `origClientOrderId`, else a conditional order
by `clientAlgoId`. Built `VALIDATE_ONLY`, as every read is (`GetOpenOrdersQueryHandler`).
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_order.query import (
    GetOrderQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_submission_mode import (
    OrderSubmissionMode,
)

logger = logging.getLogger("App.QueryHandler")


class GetOrderQueryHandler(IQueryHandler[GetOrderQuery, Order | None]):
    def __init__(self, contexts: IVenueContexts) -> None:
        self._contexts = contexts

    def execute(self, query: GetOrderQuery) -> Order | None:
        logger.debug(
            "Handling GetOrderQuery on %s for %s",
            query.venue.value,
            query.client_order_id,
        )
        client = self._contexts.get(query.venue).client_factory.create(
            OrderSubmissionMode.VALIDATE_ONLY
        )
        return client.find_order(query.symbol, query.client_order_id)
