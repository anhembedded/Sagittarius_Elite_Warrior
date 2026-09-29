"""Application port for caching live order-rounding symbol metadata
(`EPIC-021C`/`EPIC-027I`), for one venue's market.

@details Same shape as `ISymbolMarketMetadataCache` (`BOT-095E1`) — not a
reuse of it. That port is hard-typed to `SymbolMarketMetadata`, the
backtest-side float entity; caching a genuinely different, `Decimal`
entity (`SymbolOrderMetadata`) through it would be a type-level lie, not a
saved abstraction.

One instance per venue (`EPIC-028A`, ADR D2): each `VenueAssembly` builds
its own, and `VenueContext.metadata_cache` hands it out. A Futures symbol and
a Spot symbol can share the same string (`BTCUSDT` names two different
instruments), and both venues can now be live in one process — keeping the
caches apart, rather than keying one shared cache by `(TradingVenue,
symbol)`, is what keeps the bare `symbol` key safe. The guard
`test_only_the_venue_assembly_constructs_venue_adapters.py` stops a second,
shared instance from appearing.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    SymbolOrderMetadata,
)


class ISymbolOrderMetadataCache(ABC):
    """Port for in-memory and persistent live order-rounding metadata
    caches."""

    @abstractmethod
    def get(self, symbol: str) -> SymbolOrderMetadata | None:
        """Retrieves cached metadata for a symbol if present."""

    @abstractmethod
    def put(self, metadata: SymbolOrderMetadata) -> None:
        """Stores or updates metadata for a symbol."""

    @abstractmethod
    def has(self, symbol: str) -> bool:
        """Checks if metadata for a symbol exists in cache."""

    @abstractmethod
    def clear(self) -> None:
        """Empties the cache."""
