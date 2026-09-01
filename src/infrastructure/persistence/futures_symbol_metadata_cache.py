"""Thread-safe in-memory cache for `FuturesSymbolMetadata` snapshots
(`EPIC-021C`)."""

from __future__ import annotations

import threading

from Sagittarius_Elite_Warrior.src.application.ports.i_futures_symbol_metadata_cache import (
    IFuturesSymbolMetadataCache,
)
from Sagittarius_Elite_Warrior.src.domain.entities.futures_symbol_metadata import (
    FuturesSymbolMetadata,
)


class InMemoryFuturesSymbolMetadataCache(IFuturesSymbolMetadataCache):
    """Thread-safe in-memory implementation of `IFuturesSymbolMetadataCache`."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cache: dict[str, FuturesSymbolMetadata] = {}

    def get(self, symbol: str) -> FuturesSymbolMetadata | None:
        with self._lock:
            return self._cache.get(symbol.upper())

    def put(self, metadata: FuturesSymbolMetadata) -> None:
        with self._lock:
            self._cache[metadata.symbol.upper()] = metadata

    def has(self, symbol: str) -> bool:
        with self._lock:
            return symbol.upper() in self._cache

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
