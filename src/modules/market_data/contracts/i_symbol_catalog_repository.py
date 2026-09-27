"""Port for storing and retrieving the local tradeable symbol catalog."""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType


class ISymbolCatalogRepository(ABC):
    """Abstraction for reading and persisting tradeable symbol listings."""

    @abstractmethod
    def get_symbols(self, market: MarketType) -> list[str]:
        """Returns the list of cached tradeable symbols of one market
        (`EPIC-027D`: Spot and USD-M Futures are separate catalogs).

        @return List of symbol tickers (e.g. ['BTCUSDT', 'ETHUSDT']), or empty list if none cached.
        """

    @abstractmethod
    def save_symbols(self, market: MarketType, symbols: list[str]) -> None:
        """Persists one market's list of tradeable symbols to local storage.

        @param symbols List of symbol tickers to persist.
        """
