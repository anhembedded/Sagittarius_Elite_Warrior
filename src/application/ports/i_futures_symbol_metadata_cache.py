"""Application port for caching USD-M Futures symbol metadata (`EPIC-021C`).

@details Same shape as `ISymbolMarketMetadataCache` (`BOT-095E1`) — not a
reuse of it. That port is hard-typed to `SymbolMarketMetadata`, the spot
entity; caching a genuinely different entity (`FuturesSymbolMetadata`)
through it would be a type-level lie, not a saved abstraction.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.domain.entities.futures_symbol_metadata import (
    FuturesSymbolMetadata,
)


class IFuturesSymbolMetadataCache(ABC):
    """Port for in-memory and persistent futures metadata caches."""

    @abstractmethod
    def get(self, symbol: str) -> FuturesSymbolMetadata | None:
        """Retrieves cached metadata for a symbol if present."""

    @abstractmethod
    def put(self, metadata: FuturesSymbolMetadata) -> None:
        """Stores or updates metadata for a symbol."""

    @abstractmethod
    def has(self, symbol: str) -> bool:
        """Checks if metadata for a symbol exists in cache."""

    @abstractmethod
    def clear(self) -> None:
        """Empties the cache."""
