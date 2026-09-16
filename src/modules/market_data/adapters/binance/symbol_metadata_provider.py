"""`BUG-127` — `ISymbolMetadataProvider` over `IExchangeClient`'s catalog read.

Mirrors `modules/trading/adapters/binance/futures_metadata_provider.py`, which
has run the same shape since `EPIC-021C` and is why order rounding on the live
path works. Applying that rather than inventing one is `ONBOARDING` §12.5
principle 5, and the two providers are deliberately near-identical so a reader
of either recognises the other.

@par Why the client arrives as a factory
`BUG-045`: constructing `PythonBinanceClient` performs a network call, and this
provider is resolved while a *screen* is being built. `SymbolCatalogService`
takes the same precaution for the same reason, in the same module — a port that
opens a socket when it is resolved breaks `BUG-107`'s rule that opening a screen
must not open a connection. Nothing is built until a read actually has to leave
the process.

@par Staleness is honoured here, unlike the first time this pattern shipped
`BUG-098` is the warning: `is_stale()` existed for a whole epic on the futures
twin and was never called, so a cached filter was trusted for the life of the
process even after Binance changed it server-side. `get_or_fetch()` therefore
treats a stale entry as a miss.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_exchange_client import (
    IExchangeClient,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_symbol_market_metadata_cache import (
    ISymbolMarketMetadataCache,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_symbol_metadata_provider import (
    ISymbolMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.symbol_market_metadata import (
    SymbolMarketMetadata,
)

logger = logging.getLogger("App.SymbolMetadata")


class BinanceSymbolMetadataProvider(ISymbolMetadataProvider):
    """Cache-first symbol filters, fetched from the exchange's catalog."""

    def __init__(
        self,
        exchange_client: Callable[[], IExchangeClient],
        cache: ISymbolMarketMetadataCache,
    ) -> None:
        self._exchange_client = exchange_client
        self._cache = cache

    def get_or_fetch(self, symbol: str) -> SymbolMarketMetadata | None:
        cached = self._cache.get(symbol)
        if cached is not None and not cached.is_stale():
            return cached
        self.refresh()
        return self._cache.get(symbol)

    def refresh(self) -> int:
        entries = self._exchange_client().get_symbol_metadata()
        for entry in entries:
            self._cache.put(entry)
        # `INFO` and once per refresh, not per symbol: a catalog is ~2,500
        # entries, and `SignalLogHandler` mirrors every `App.*` INFO line to the
        # UI's queued log model (`BUG-042`, `ONBOARDING` §8 trap 9).
        logger.info("Symbol metadata refreshed: %d symbols cached.", len(entries))
        return len(entries)
