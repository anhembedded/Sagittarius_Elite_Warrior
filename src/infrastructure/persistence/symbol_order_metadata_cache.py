"""Thread-safe in-memory cache for `SymbolOrderMetadata` snapshots
(`EPIC-021C`/`EPIC-027I`) — one instance serves whichever single market
the active `TradingVenue` trades; see `ISymbolOrderMetadataCache`'s own
docstring for why that makes a bare `symbol` key safe here."""

from __future__ import annotations

import threading

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_symbol_order_metadata_cache import (
    ISymbolOrderMetadataCache,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    SymbolOrderMetadata,
)


class InMemorySymbolOrderMetadataCache(ISymbolOrderMetadataCache):
    """Thread-safe in-memory implementation of `ISymbolOrderMetadataCache`."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cache: dict[str, SymbolOrderMetadata] = {}

    def get(self, symbol: str) -> SymbolOrderMetadata | None:
        with self._lock:
            return self._cache.get(symbol.upper())

    def put(self, metadata: SymbolOrderMetadata) -> None:
        with self._lock:
            self._cache[metadata.symbol.upper()] = metadata

    def has(self, symbol: str) -> bool:
        with self._lock:
            return symbol.upper() in self._cache

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
