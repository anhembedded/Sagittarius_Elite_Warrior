"""`EPIC-027I` — `IMarketMetadataProvider` implementation: fetches Spot
`exchangeInfo` through `SpotSessionFactory` and caches it."""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.metadata_reads import (
    catalog_read_failures,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_metadata_parser import (
    parse_spot_exchange_info,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_session_factory import (
    SpotSessionFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_market_metadata_provider import (
    IMarketMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_symbol_order_metadata_cache import (
    ISymbolOrderMetadataCache,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    SymbolOrderMetadata,
)

logger = logging.getLogger("App.SpotMetadata")


class SpotMetadataProvider(IMarketMetadataProvider):
    """@brief Cache-first Spot metadata provider — the Spot half of
    `IMarketMetadataProvider`'s venue-branching bind (`ITradingAccountReader`
    mirrors the same pattern, `EPIC-027H`)."""

    def __init__(
        self,
        session_factory: SpotSessionFactory,
        cache: ISymbolOrderMetadataCache,
    ) -> None:
        self._session_factory = session_factory
        self._cache = cache

    def get_or_fetch(self, symbol: str) -> SymbolOrderMetadata | None:
        cached = self._cache.get(symbol)
        if cached is not None and not cached.is_stale():
            return cached
        self.refresh()
        return self._cache.get(symbol)

    def refresh(self) -> None:
        with catalog_read_failures("Spot symbol rules"):
            client = self._session_factory.create_metadata_client()
            payload = client.get_exchange_info()
        entries = parse_spot_exchange_info(payload)
        for entry in entries:
            self._cache.put(entry)
        logger.info("Spot exchangeInfo refreshed: %d symbols cached.", len(entries))
