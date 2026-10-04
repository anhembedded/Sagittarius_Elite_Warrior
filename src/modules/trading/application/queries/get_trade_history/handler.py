"""`EPIC-028E` — `GetTradeHistoryQueryHandler`.

@details Reads the venue's own `IAccountHistoryReader`: the one symbol asked
for, or every symbol the reader names as active. Binance's history endpoints
need a symbol, so "every symbol" is that list, and the page carries it as
`scanned_symbols` for the screen to show.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.modules.trading.application.history_paging import (
    PageRequest,
    newest_first_page,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.history_scope import (
    history_scope,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_trade_history.query import (
    GetTradeHistoryQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.history_page import (
    HistoryPage,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trade_record import (
    TradeRecord,
)

logger = logging.getLogger("App.QueryHandler")


class GetTradeHistoryQueryHandler(
    IQueryHandler[GetTradeHistoryQuery, HistoryPage[TradeRecord]]
):
    def __init__(self, contexts: IVenueContexts) -> None:
        self._contexts = contexts

    def execute(self, query: GetTradeHistoryQuery) -> HistoryPage[TradeRecord]:
        reader = self._contexts.get(query.venue).history_reader
        scope = history_scope(reader, query.symbol, query.since)
        symbols = scope.symbols
        logger.debug(
            "Handling GetTradeHistoryQuery on %s: %s since %s, page %d",
            query.venue.value,
            ", ".join(symbols) or "no active symbol",
            query.since.isoformat(),
            query.page,
        )
        rows = [
            row
            for symbol in symbols
            for row in reader.trade_history(symbol, query.since)
        ]
        return newest_first_page(
            rows,
            lambda row: (row.time, row.trade_id),
            PageRequest(
                page=query.page,
                scanned_symbols=symbols,
                notices=(() if query.symbol else reader.known_gaps().every_symbol)
                + scope.notices,
            ),
        )
