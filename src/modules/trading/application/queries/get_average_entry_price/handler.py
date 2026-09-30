"""`EPIC-028E` — `GetAverageEntryPriceQueryHandler`.

@details Two reads from the addressed venue, then the pure
`average_entry_price` policy: the holding from the connection check the
venue already makes (`ITradingAccountReader`, as `GetHoldingsQueryHandler`
reads it) and the fills from `IAccountHistoryReader`. No holding, or fills
that do not explain it, answers `None`. A Futures venue has no holdings
(`ExchangeConnectionStatus.holdings` is `None` there) and so always answers
`None`: its positions carry the exchange's own entry price.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_average_entry_price.query import (
    QUOTE_ASSET,
    GetAverageEntryPriceQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.average_entry_price import (
    AverageEntryPrice,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.average_entry_price import (
    HeldPair,
    average_entry_price,
)

logger = logging.getLogger("App.QueryHandler")


class GetAverageEntryPriceQueryHandler(
    IQueryHandler[GetAverageEntryPriceQuery, AverageEntryPrice | None]
):
    def __init__(self, contexts: IVenueContexts) -> None:
        self._contexts = contexts

    def execute(self, query: GetAverageEntryPriceQuery) -> AverageEntryPrice | None:
        context = self._contexts.get(query.venue)
        holdings = context.account_reader.check_connection().holdings or ()
        holding = next((h for h in holdings if h.asset == query.base_asset), None)
        if holding is None or holding.is_dust:
            logger.debug(
                "No %s holding on %s; no average entry price",
                query.base_asset,
                query.venue.value,
            )
            return None
        fills = context.history_reader.trade_history(query.symbol, query.since)
        answer = average_entry_price(
            fills,
            HeldPair(
                symbol=query.symbol,
                base_asset=query.base_asset,
                quote_asset=QUOTE_ASSET,
                held_quantity=holding.total,
                tolerance=holding.dust_threshold,
            ),
        )
        if answer is None:
            logger.debug(
                "%d fills on %s since %s do not account for the %s held; "
                "no average entry price",
                len(fills),
                query.symbol,
                query.since.isoformat(),
                holding.total,
            )
        return answer
