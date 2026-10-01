"""`EPIC-028O` — `GetMarkPriceQueryHandler`: the addressed venue's mark-price
reader answers. A venue with no reader (Spot) answers
`NotApplicable.ON_THIS_VENUE`, never its last price passed off as a mark."""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_mark_price.query import (
    GetMarkPriceQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.mark_price import (
    MarkPrice,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.not_applicable import (
    NotApplicable,
)

logger = logging.getLogger("App.QueryHandler")


class GetMarkPriceQueryHandler(
    IQueryHandler[GetMarkPriceQuery, MarkPrice | NotApplicable]
):
    def __init__(self, contexts: IVenueContexts) -> None:
        self._contexts = contexts

    def execute(self, query: GetMarkPriceQuery) -> MarkPrice | NotApplicable:
        source = self._contexts.get(query.venue).mark_price_reader
        if source is None:
            logger.debug(
                "GetMarkPriceQuery for %s on %s: the venue has no mark price",
                query.symbol,
                query.venue.value,
            )
            return NotApplicable.ON_THIS_VENUE
        logger.debug(
            "Handling GetMarkPriceQuery for %s on %s", query.symbol, query.venue.value
        )
        return source.mark_price(query.symbol)
