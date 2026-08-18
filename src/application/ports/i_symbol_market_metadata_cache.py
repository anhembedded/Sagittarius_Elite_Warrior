"""Application port for querying and caching symbol market metadata snapshots (BOT-095E1)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.domain.entities.symbol_market_metadata import (
    SymbolMarketMetadata,
)


class ISymbolMarketMetadataCache(ABC):
    """Port for in-memory and persistent exchange metadata caches."""

    @abstractmethod
    def get(self, symbol: str) -> SymbolMarketMetadata | None:
        """Retrieves cached metadata for a symbol if present."""

    @abstractmethod
    def put(self, metadata: SymbolMarketMetadata) -> None:
        """Stores or updates metadata for a symbol."""

    @abstractmethod
    def has(self, symbol: str) -> bool:
        """Checks if metadata for a symbol exists in cache."""

    @abstractmethod
    def clear(self) -> None:
        """Empties the cache."""
