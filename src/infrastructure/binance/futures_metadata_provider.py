"""`EPIC-021C` — `IMarketMetadataProvider` implementation: fetches USD-M
Futures `exchangeInfo` through `ExchangeSessionFactory` and caches it."""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.application.ports.i_futures_symbol_metadata_cache import (
    IFuturesSymbolMetadataCache,
)
from Sagittarius_Elite_Warrior.src.application.ports.i_market_metadata_provider import (
    IMarketMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.domain.entities.futures_symbol_metadata import (
    FuturesSymbolMetadata,
)
from Sagittarius_Elite_Warrior.src.infrastructure.binance.exchange_session_factory import (
    ExchangeSessionFactory,
)
from Sagittarius_Elite_Warrior.src.infrastructure.binance.futures_metadata_parser import (
    parse_futures_exchange_info,
)

logger = logging.getLogger("App.FuturesMetadata")


class FuturesMetadataProvider(IMarketMetadataProvider):
    """@brief Cache-first futures metadata provider.
    @details `session_factory` need not be (and, in production, is not)
    scoped to `MarketDataVenue.FUTURES_TESTNET` itself — see
    `ExchangeSessionFactory.create_futures_metadata_client()`'s own
    docstring for why futures metadata always ignores that setting.
    """

    def __init__(
        self,
        session_factory: ExchangeSessionFactory,
        cache: IFuturesSymbolMetadataCache,
    ) -> None:
        self._session_factory = session_factory
        self._cache = cache

    def get_or_fetch(self, symbol: str) -> FuturesSymbolMetadata | None:
        cached = self._cache.get(symbol)
        # `BUG-098` — `FuturesSymbolMetadata.is_stale()` existed since
        # `BOT-095E1` and was never called anywhere in production: once a
        # symbol was cached, its `stepSize`/`tickSize`/`minNotional` were
        # trusted for the rest of the process, even after Binance changes
        # an exchange filter server-side. A 24h-old entry now forces a
        # real refresh instead of being trusted forever.
        if cached is not None and not cached.is_stale():
            return cached
        self.refresh()
        return self._cache.get(symbol)

    def refresh(self) -> None:
        client = self._session_factory.create_futures_metadata_client()
        payload = client.futures_exchange_info()
        entries = parse_futures_exchange_info(payload)
        for entry in entries:
            self._cache.put(entry)
        logger.info("Futures exchangeInfo refreshed: %d symbols cached.", len(entries))
