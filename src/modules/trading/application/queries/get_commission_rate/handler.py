"""`EPIC-028F` — `GetCommissionRateQueryHandler`: the addressed venue's own
commission reader answers. A failure raises `CommissionRateUnavailableError`
rather than answering a guessed rate."""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_commission_rate.query import (
    GetCommissionRateQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.commission_rate import (
    CommissionRate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)

logger = logging.getLogger("App.QueryHandler")


class GetCommissionRateQueryHandler(
    IQueryHandler[GetCommissionRateQuery, CommissionRate]
):
    def __init__(self, contexts: IVenueContexts) -> None:
        self._contexts = contexts

    def execute(self, query: GetCommissionRateQuery) -> CommissionRate:
        logger.debug(
            "Handling GetCommissionRateQuery for %s on %s",
            query.symbol,
            query.venue.value,
        )
        return self._contexts.get(query.venue).commission_reader.commission_rate(
            query.symbol
        )
