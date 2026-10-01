"""`EPIC-028O` — reads the best bid and ask on one venue's book.

@details Public market data, so no credentials: Futures
`GET /fapi/v1/ticker/bookTicker`, Spot `GET /api/v3/ticker/bookTicker`. The
desk's price button fills the best bid or ask from it, and a Futures market
order's open loss is priced against it (`EPIC-028G` §3).

Plausible extensions, each one implementation behind this port: a reader
fed by the `@bookTicker` stream instead of a REST read per click; a mainnet
venue (another `VenueContext`, nothing here).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.best_bid_ask import (
    BestBidAsk,
)


class IBookTickerReader(ABC):
    """One venue's best bid and ask, read from the exchange."""

    @abstractmethod
    def best_bid_ask(self, symbol: str) -> BestBidAsk:
        """@brief The best bid and ask on `symbol`'s book now.
        @throws MarketPriceUnavailableError The exchange did not answer, or
        does not list `symbol`."""
