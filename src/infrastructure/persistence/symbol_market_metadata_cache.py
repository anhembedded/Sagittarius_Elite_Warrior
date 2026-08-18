"""Thread-safe in-memory cache for SymbolMarketMetadata snapshots (BOT-095E1)."""

from __future__ import annotations

import threading

from Sagittarius_Elite_Warrior.src.application.ports.i_symbol_market_metadata_cache import (
    ISymbolMarketMetadataCache,
)
from Sagittarius_Elite_Warrior.src.domain.entities.symbol_market_metadata import (
    SymbolMarketMetadata,
)


class InMemorySymbolMarketMetadataCache(ISymbolMarketMetadataCache):
    """Thread-safe in-memory implementation of ISymbolMarketMetadataCache."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cache: dict[str, SymbolMarketMetadata] = {}

    def get(self, symbol: str) -> SymbolMarketMetadata | None:
        with self._lock:
            return self._cache.get(symbol.upper())

    def put(self, metadata: SymbolMarketMetadata) -> None:
        with self._lock:
            self._cache[metadata.symbol.upper()] = metadata

    def has(self, symbol: str) -> bool:
        with self._lock:
            return symbol.upper() in self._cache

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
