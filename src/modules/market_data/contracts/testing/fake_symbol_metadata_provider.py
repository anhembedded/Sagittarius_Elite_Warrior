"""The verified fake for `ISymbolMetadataProvider` (HLD §10.3, `BUG-127`).

**Who needs it.** `DataSyncCoordinator` calls `get_or_fetch()` on its worker
thread, and this is a *foreign* port to the Backtest screen — so
`Mock(spec=ISymbolMetadataProvider)` is not an option
(`test_no_foreign_port_is_mocked.py` fails on it, and `CS-001` is what a loose
stand-in cost this repository already).

**Scripted, and it counts the round trips.** A test says which symbols the
"exchange" knows; `get_or_fetch()` then behaves the way the real provider does —
cache-first, with a fetch on a miss — and `fetch_count` records how many times it
went out. That counter is the point: the consumer's whole reason to call this on
a worker rather than on the Qt main thread is that a fetch is a network round
trip, and a fake that hid the round trips could not show a test that the second
read is free.

**It refuses a script the real provider could not produce.** `knows()` rejects a
`SymbolMarketMetadata` whose symbol does not match the key it is filed under,
because the real cache is keyed by `metadata.symbol` and a test scripting a
mismatch would be asserting against an answer production cannot give.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_symbol_metadata_provider import (
    ISymbolMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.symbol_market_metadata import (
    SymbolMarketMetadata,
)


class FakeSymbolMetadataProvider(ISymbolMetadataProvider):
    """In-memory `ISymbolMetadataProvider`: scripted catalog, counted fetches."""

    def __init__(self) -> None:
        self._catalog: dict[str, SymbolMarketMetadata] = {}
        self._cached: dict[str, SymbolMarketMetadata] = {}
        #: How many times a read had to leave the "exchange". Read by tests that
        #: care the second one is free.
        self.fetch_count = 0

    def knows(self, metadata: SymbolMarketMetadata) -> None:
        """Script one symbol into the "exchange" this fake stands for."""
        symbol = metadata.symbol.upper()
        if not symbol:
            raise ValueError("a scripted metadata entry must name its symbol")
        self._catalog[symbol] = metadata

    def get_or_fetch(self, symbol: str) -> SymbolMarketMetadata | None:
        key = symbol.upper()
        cached = self._cached.get(key)
        if cached is not None and not cached.is_stale():
            return cached
        self.refresh()
        return self._cached.get(key)

    def refresh(self) -> int:
        self.fetch_count += 1
        self._cached = dict(self._catalog)
        return len(self._cached)
