"""Port for storing and retrieving the local tradeable symbol catalog."""

from __future__ import annotations

from abc import ABC, abstractmethod


class ISymbolCatalogRepository(ABC):
    """Abstraction for reading and persisting tradeable symbol listings."""

    @abstractmethod
    def get_symbols(self) -> list[str]:
        """Returns the list of cached tradeable symbols.

        @return List of symbol tickers (e.g. ['BTCUSDT', 'ETHUSDT']), or empty list if none cached.
        """

    @abstractmethod
    def save_symbols(self, symbols: list[str]) -> None:
        """Persists the list of tradeable symbols to local storage.

        @param symbols List of symbol tickers to persist.
        """
