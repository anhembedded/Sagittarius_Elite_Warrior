"""Port: *what are this symbol's exchange order rules?* (`BUG-127`, HLD §3.4).

**Why a provider next to the cache, rather than a richer cache.**
`ISymbolMarketMetadataCache` is a store — `get`/`put`/`has`/`clear`, and `get()`
promises only "if present". Teaching it to fetch would make a cache read able to
perform a network call, which is precisely the surprise `BUG-045` and `BUG-107`
were about (opening a screen must not open a connection). So the two concerns
stay two objects, and this is the one that may leave the process.

This is not invention: `trading` has run the identical split since `EPIC-021C` —
`IFuturesSymbolMetadataCache` stores, `IMarketMetadataProvider` fetches and
caches — and that pair is why order rounding on the live path works. `BUG-127`
was the market-data twin having only the store half wired, and not even that:
nothing bound it and nothing filled it, so the Backtest screen's exchange-rule
check answered *"not verified"* for every symbol from the day it shipped.

@par Two operations, deliberately
`get_or_fetch()` is the cache-first path a consumer uses when it wants an answer
and does not care where from. `refresh()` is the explicit "go to the exchange
now" a background worker calls — the Backtest screen's data sync is the first
one, because that worker is already off the main thread and already about *this
symbol*. Binance answers `exchangeInfo` for the whole catalog in one call, so
there is no cheaper per-symbol refresh to offer instead, and `refresh()`
therefore warms every symbol at once as a side effect worth knowing about.

@par What a consumer must be ready for
`None` means *this symbol is not in the catalog, even after a fetch* — never a
placeholder standing in for a symbol that was never found (`domain-truth-rule.md`:
a convenience must not be presented as a fact). A caller that cannot fetch —
because it runs on the UI thread — reads the **cache** instead and says
"not verified yet", which is then a true transient state rather than a permanent
falsehood.

@par The seam this leaves open
A second venue (futures spot-margin, another exchange) is a second implementation
of this port, bound in `composition/port_bindings.py` on the venue already in
`MarketDataVenue` — no consumer changes. A *filtered* catalog read (only USDT
pairs, say) would be a new method here, not a parameter on these two: PR 1.2 left
`quote_asset` out of `ISymbolCatalog` for exactly that reason, and nothing
filters yet.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.symbol_market_metadata import (
    SymbolMarketMetadata,
)


class ISymbolMetadataProvider(ABC):
    """One symbol's price, lot and notional filters, cache-first."""

    @abstractmethod
    def get_or_fetch(self, symbol: str) -> SymbolMarketMetadata | None:
        """@brief Cached metadata for `symbol`, fetching the whole catalog
        first if the cache holds nothing for it.

        @return `None` when `symbol` does not exist in the catalog even after a
        fetch. May perform a network call, so never call it on the Qt main
        thread.
        """

    @abstractmethod
    def refresh(self) -> int:
        """@brief Unconditionally re-fetches the catalog and repopulates the
        cache.

        @return How many symbols were cached — the number a caller logs, and
        the one a test asserts against instead of reaching into the cache.
        """
