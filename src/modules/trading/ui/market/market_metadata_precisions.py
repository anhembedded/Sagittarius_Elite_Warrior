"""`MarketMetadataPrecisions` — the chosen market's tick and step sizes, from
the market-data catalog already read, as the precisions the Watchlist writes
prices and volumes in (`EPIC-033N`).

It reads `ISymbolMarketMetadataCache` and never the network: the table asks on
the UI thread, on every paint. The market is asked each time, so a switch to
Futures quotes the same symbol in Futures' filters (`EPIC-027C`: a symbol's
filters differ between Spot and Futures). `WatchlistFilters` fills the cache
when the Watchlist goes live; until then every symbol is unknown and its cells
keep the formatter's magnitude rule.
"""

from __future__ import annotations

from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_symbol_market_metadata_cache import (
    ISymbolMarketMetadataCache,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.filter_precisions import (
    precision_of,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.i_symbol_precisions import (
    ISymbolPrecisions,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import Precision


class MarketMetadataPrecisions(ISymbolPrecisions):
    """The cached `SymbolMarketMetadata` of the market `market()` names."""

    def __init__(
        self, cache: ISymbolMarketMetadataCache, market: Callable[[], MarketType]
    ) -> None:
        self._cache = cache
        self._market = market

    def tick(self, symbol: str) -> Precision | None:
        metadata = self._cache.get(self._market(), symbol)
        return (
            None if metadata is None else precision_of(metadata.price_filter.tick_size)
        )

    def step(self, symbol: str) -> Precision | None:
        metadata = self._cache.get(self._market(), symbol)
        return (
            None
            if metadata is None
            else precision_of(metadata.lot_size_filter.step_size)
        )
