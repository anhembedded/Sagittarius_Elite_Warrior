"""`OrderMetadataPrecisions` — a venue's tick and step sizes, from the order
metadata it has already read, as the precisions its desk's tables write
prices and quantities in (`EPIC-033N`).

It reads the venue's `ISymbolOrderMetadataCache` and never the network: a
table asks on the UI thread, on every paint. The cache fills when the desk
first reads a symbol's order terms, which fetches the venue's whole catalog
(`IMarketMetadataProvider.get_or_fetch`); until then every symbol is unknown
and its cells keep the formatter's magnitude rule. A stale entry still
answers: a tick size changes rarely, and the order path re-reads it before an
order is shaped.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_symbol_order_metadata_cache import (
    ISymbolOrderMetadataCache,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.i_symbol_precisions import (
    ISymbolPrecisions,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import Precision


def precision_of(quantum: Decimal | float) -> Precision | None:
    """A filter's size as a `Precision`; `None` for a size of zero, which is
    Binance's "this filter does not restrict" and says nothing of decimals."""
    exact = quantum if isinstance(quantum, Decimal) else Decimal(repr(quantum))
    if not exact.is_finite() or exact <= 0:
        return None
    return Precision(exact)


class OrderMetadataPrecisions(ISymbolPrecisions):
    """One venue's cached `SymbolOrderMetadata`, as display precisions."""

    def __init__(self, cache: ISymbolOrderMetadataCache) -> None:
        self._cache = cache

    def tick(self, symbol: str) -> Precision | None:
        metadata = self._cache.get(symbol)
        return None if metadata is None else precision_of(metadata.tick_size)

    def step(self, symbol: str) -> Precision | None:
        metadata = self._cache.get(symbol)
        return None if metadata is None else precision_of(metadata.step_size)
