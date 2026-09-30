"""`EPIC-028E` — which of some candidate symbols the exchange lists, for at
most one catalog download per unknown symbol.

@details `SpotHistoryReader.active_symbols` turns every held asset into its
USDT pair and must drop the pairs that do not exist: asking `myTrades` for one
is an error. `IMarketMetadataProvider.get_or_fetch` answers that, but it
downloads the whole `exchangeInfo` catalog on every cache miss, and an
unlisted pair always misses — a testnet account holding a handful of such
assets downloaded the catalog once per asset per call (the PR #297 review,
finding 1; weight 20 and several megabytes each on the real endpoint).

Here a miss refreshes the catalog once for all candidates together, and a
symbol still missing afterwards is remembered as unlisted, so later calls ask
the exchange again only for a symbol never seen before. A symbol listed later
is picked up as soon as anything refreshes the shared cache (the metadata
provider's own trading path does); a pair delisted after it was cached stays
counted until the cache is cleared.
"""

from __future__ import annotations

import threading
from collections.abc import Iterable

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_market_metadata_provider import (
    IMarketMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_symbol_order_metadata_cache import (
    ISymbolOrderMetadataCache,
)


class ListedSymbols:
    """Answers "which of these does the exchange list" from one venue's
    metadata cache, refreshing it only for symbols not yet known either way."""

    def __init__(
        self, provider: IMarketMetadataProvider, cache: ISymbolOrderMetadataCache
    ) -> None:
        self._provider = provider
        self._cache = cache
        self._lock = threading.Lock()
        self._unlisted: set[str] = set()

    def among(self, candidates: Iterable[str]) -> set[str]:
        """@return The listed subset of `candidates`.
        @throws Whatever the provider's refresh raises; the caller translates
        it."""
        wanted = set(candidates)
        with self._lock:
            unknown = {
                symbol
                for symbol in wanted - self._unlisted
                if not self._cache.has(symbol)
            }
            if unknown:
                self._provider.refresh()
                self._unlisted |= {s for s in unknown if not self._cache.has(s)}
            return {symbol for symbol in wanted if self._cache.has(symbol)}
