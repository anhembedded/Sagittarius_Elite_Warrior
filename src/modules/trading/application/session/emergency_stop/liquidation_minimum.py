"""`EPIC-029` ADR D6 r2 — the smallest part of a split liquidation the
venue accepts.

@details Emergency Stop splits one asset's sale per bot
(`split_liquidation`). The split can cut a part the whole sale never had,
such as one lot step left untagged, which the venue's `NOTIONAL` filter
rejects; that rejection stops the sale of every asset after it (the
`EPIC-029A` review). So a split part below the exchange minimum is left
held as dust instead of being sent.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_book_ticker_reader import (
    IBookTickerReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.market_price_unavailable_error import (
    MarketPriceUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    SymbolOrderMetadata,
)

logger = logging.getLogger("App.CommandHandler")


def min_split_quantity(
    book_ticker: IBookTickerReader, metadata: SymbolOrderMetadata
) -> Decimal:
    """@brief The symbol's minimum notional at the best bid, in base.
    @return Zero when there is no bid to price it with: the venue then
    judges each part, as it judges an unsplit sale."""
    try:
        book = book_ticker.best_bid_ask(metadata.symbol)
    except MarketPriceUnavailableError as exc:
        logger.warning(
            "No bid for %s; liquidation parts sent unchecked: %s", metadata.symbol, exc
        )
        return Decimal(0)
    if not book.has_bid:
        logger.warning(
            "No bid for %s; liquidation parts sent unchecked.", metadata.symbol
        )
        return Decimal(0)
    return metadata.min_notional / book.bid_price
