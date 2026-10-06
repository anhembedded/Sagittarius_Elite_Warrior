"""`EPIC-028E` — `GetOrderHistoryQueryHandler`.

@details Reads the venue's own `IAccountHistoryReader`: the one symbol asked
for, or every symbol the reader names as active. Binance's history endpoints
need a symbol, so "every symbol" is that list, and the page carries it as
`scanned_symbols` for the screen to show. `history_scope` bounds that list
by Binance's request weight and names the pairs it left out (`BUG-145`).
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
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_order_history.query import (
    GetOrderHistoryQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.history_gaps import (
    HistoryGaps,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.history_page import (
    HistoryPage,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_record import (
    OrderRecord,
)

logger = logging.getLogger("App.QueryHandler")


def _notices(gaps: HistoryGaps, *, every_symbol: bool) -> tuple[str, ...]:
    """`EPIC-028Q` — the venue's order-history gaps, and its every-symbol
    gaps when the page covers every symbol."""
    return gaps.order_history + (gaps.every_symbol if every_symbol else ())


class GetOrderHistoryQueryHandler(
    IQueryHandler[GetOrderHistoryQuery, HistoryPage[OrderRecord]]
):
    def __init__(self, contexts: IVenueContexts) -> None:
        self._contexts = contexts

    def execute(self, query: GetOrderHistoryQuery) -> HistoryPage[OrderRecord]:
        reader = self._contexts.get(query.venue).history_reader
        scope = history_scope(reader, query.symbol, query.since, query.desk_symbol)
        symbols = scope.symbols
        logger.debug(
            "Handling GetOrderHistoryQuery on %s: %s since %s, page %d",
            query.venue.value,
            ", ".join(symbols) or "no active symbol",
            query.since.isoformat(),
            query.page,
        )
        rows = [
            row
            for symbol in symbols
            for row in reader.order_history(symbol, query.since)
        ]
        return newest_first_page(
            rows,
            lambda row: (row.created_at, row.order.client_order_id),
            PageRequest(
                page=query.page,
                scanned_symbols=symbols,
                notices=_notices(reader.known_gaps(), every_symbol=not query.symbol)
                + scope.notices,
            ),
        )
