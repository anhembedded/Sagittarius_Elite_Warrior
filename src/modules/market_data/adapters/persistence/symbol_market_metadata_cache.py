"""Thread-safe in-memory cache for SymbolMarketMetadata snapshots (BOT-095E1)."""

from __future__ import annotations

import threading

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_symbol_market_metadata_cache import (
    ISymbolMarketMetadataCache,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.symbol_market_metadata import (
    SymbolMarketMetadata,
)


class InMemorySymbolMarketMetadataCache(ISymbolMarketMetadataCache):
    """Thread-safe in-memory implementation of ISymbolMarketMetadataCache."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cache: dict[tuple[MarketType, str], SymbolMarketMetadata] = {}

    def get(self, market: MarketType, symbol: str) -> SymbolMarketMetadata | None:
        with self._lock:
            return self._cache.get((market, symbol.upper()))

    def put(self, market: MarketType, metadata: SymbolMarketMetadata) -> None:
        with self._lock:
            self._cache[(market, metadata.symbol.upper())] = metadata

    def has(self, market: MarketType, symbol: str) -> bool:
        with self._lock:
            return (market, symbol.upper()) in self._cache

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
