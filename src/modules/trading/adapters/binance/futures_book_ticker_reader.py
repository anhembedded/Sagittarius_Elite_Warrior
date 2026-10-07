"""`EPIC-028O` — `IBookTickerReader` for USD-M Futures:
`GET /fapi/v1/ticker/bookTicker?symbol=`, unsigned."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_session_factory import (
    FuturesSessionFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.market_price_reads import (
    market_price_answer,
    parse_book_ticker,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.best_bid_ask import (
    BestBidAsk,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_book_ticker_reader import (
    IBookTickerReader,
)


class FuturesBookTickerReader(IBookTickerReader):
    """Reads its Futures venue's book, best bid and ask."""

    def __init__(self, session_factory: FuturesSessionFactory) -> None:
        self._session_factory = session_factory

    def best_bid_ask(self, symbol: str) -> BestBidAsk:
        with market_price_answer(f"{symbol} Futures best bid and ask"):
            client = self._session_factory.create_futures_metadata_client()
            return parse_book_ticker(
                client.futures_orderbook_ticker(symbol=symbol), symbol
            )
