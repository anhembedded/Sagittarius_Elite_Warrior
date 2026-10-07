"""`EPIC-028O` — `IBookTickerReader` for Spot:
`GET /api/v3/ticker/bookTicker?symbol=`, unsigned."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.market_price_reads import (
    market_price_answer,
    parse_book_ticker,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_session_factory import (
    SpotSessionFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.best_bid_ask import (
    BestBidAsk,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_book_ticker_reader import (
    IBookTickerReader,
)


class SpotBookTickerReader(IBookTickerReader):
    """Reads its Spot venue's book, best bid and ask."""

    def __init__(self, session_factory: SpotSessionFactory) -> None:
        self._session_factory = session_factory

    def best_bid_ask(self, symbol: str) -> BestBidAsk:
        with market_price_answer(f"{symbol} Spot best bid and ask"):
            client = self._session_factory.create_metadata_client()
            return parse_book_ticker(client.get_orderbook_ticker(symbol=symbol), symbol)
