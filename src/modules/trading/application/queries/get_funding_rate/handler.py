"""`EPIC-039G` — `GetFundingRateQueryHandler`: the addressed venue's funding
reader answers. A venue with no reader (Spot) answers
`NotApplicable.ON_THIS_VENUE`: Spot has no funding, and a zero rate would be
added up as a cost of nothing."""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_funding_rate.query import (
    GetFundingRateQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.funding_rate import (
    FundingRate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.not_applicable import (
    NotApplicable,
)

logger = logging.getLogger("App.QueryHandler")


class GetFundingRateQueryHandler(
    IQueryHandler[GetFundingRateQuery, FundingRate | NotApplicable]
):
    def __init__(self, contexts: IVenueContexts) -> None:
        self._contexts = contexts

    def execute(self, query: GetFundingRateQuery) -> FundingRate | NotApplicable:
        source = self._contexts.get(query.venue).funding_reader
        if source is None:
            logger.debug(
                "GetFundingRateQuery for %s on %s: the venue has no funding",
                query.symbol,
                query.venue.value,
            )
            return NotApplicable.ON_THIS_VENUE
        logger.debug(
            "Handling GetFundingRateQuery for %s on %s", query.symbol, query.venue.value
        )
        return source.funding_rate(query.symbol)
