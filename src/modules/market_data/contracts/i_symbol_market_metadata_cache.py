"""Application port for querying and caching symbol market metadata snapshots (BOT-095E1)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.symbol_market_metadata import (
    SymbolMarketMetadata,
)


class ISymbolMarketMetadataCache(ABC):
    """Port for in-memory and persistent exchange metadata caches.

    Keyed by (market, symbol) since `EPIC-027C`: the same symbol has a
    different step size and minimum notional on Spot and on Futures."""

    @abstractmethod
    def get(self, market: MarketType, symbol: str) -> SymbolMarketMetadata | None:
        """Retrieves cached metadata for a symbol of `market` if present."""

    @abstractmethod
    def put(self, market: MarketType, metadata: SymbolMarketMetadata) -> None:
        """Stores or updates metadata for a symbol of `market`."""

    @abstractmethod
    def has(self, market: MarketType, symbol: str) -> bool:
        """Checks if metadata for a symbol of `market` exists in cache."""

    @abstractmethod
    def clear(self) -> None:
        """Empties the cache."""
