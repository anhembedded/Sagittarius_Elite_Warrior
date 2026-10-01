"""`EPIC-028O` — `GetBestBidAskQueryHandler`: the addressed venue's
book-ticker reader answers. A failure raises `MarketPriceUnavailableError`
rather than answering a guessed price."""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_best_bid_ask.query import (
    GetBestBidAskQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.best_bid_ask import (
    BestBidAsk,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)

logger = logging.getLogger("App.QueryHandler")


class GetBestBidAskQueryHandler(IQueryHandler[GetBestBidAskQuery, BestBidAsk]):
    def __init__(self, contexts: IVenueContexts) -> None:
        self._contexts = contexts

    def execute(self, query: GetBestBidAskQuery) -> BestBidAsk:
        logger.debug(
            "Handling GetBestBidAskQuery for %s on %s",
            query.symbol,
            query.venue.value,
        )
        return self._contexts.get(query.venue).book_ticker_reader.best_bid_ask(
            query.symbol
        )
