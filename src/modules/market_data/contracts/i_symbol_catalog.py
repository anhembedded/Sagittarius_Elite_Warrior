"""Port: *which symbols can I trade?* (HLD §3.4, SDD-06b).

**Why this port exists.** Two call sites ask for the exchange's tradeable
pair list — the shared symbol picker (`modules/market_data/ui/symbol_options_coordinator`,
which three screens use) and Data Management's auto-discover — and both build
`ListAvailableSymbolsQuery` and dispatch it, so both import
`modules/market_data/application/`. That is the boundary rule's one
prohibition: a consumer may import a module's `contracts/` and nothing else.

**What it fixes beyond the boundary.** The dispatched answer is untyped, so a
caller that receives `None` (no handler bound, or a test double) hands `None`
to a Qt signal declared `list` and the failure lands somewhere else entirely.
And the list was mutable: three consumers read it straight into a picker, and
one that sorted it in place changed what the next reader saw. A
`tuple[str, ...]` is the snapshot every other read on this module's edge now
returns (`domain-truth-rule.md`: a snapshot the caller cannot edit).

**`force_refresh` is here and `quote_asset` is not.** SDD-06b declares
`list_symbols(quote_asset: str | None)`. Nothing filters by quote asset
today: `ui/components/symbol_picker/quote_asset.py` splits the *whole* list in
the UI layer, where the picker's tabs live, and no caller has ever asked the
module for a subset — so publishing that parameter would be publishing a
filter nobody implements. `force_refresh`, on the other hand, is what the
picker's manual refresh button passes (`BUG-066`). The rule is HLD §2.4's,
applied the way PR 0.5 applied it when it left `days_back_if_empty` out of
`MarketDataSyncRequest`: a published contract carries what callers measurably
use, and gains a parameter when a caller needs it.

**Not the repository.** `ISymbolCatalogRepository` is this module's internal
port for *storing* the list; this one answers a question and decides for
itself whether the stored copy is good enough. A consumer that resolved the
repository would be deciding that for the module.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence


def normalised_symbols(symbols: Sequence[str]) -> tuple[str, ...]:
    """Upper-cased, trimmed, de-duplicated, sorted — the port's promise.

    **In `contracts/` rather than beside the implementation**, because it *is*
    the contract: `list_symbols()`'s docstring promises this shape, so the
    real service and the verified fake must apply the identical rule and
    neither may own it. It also keeps the direction outward — a fake living in
    `contracts/testing/` importing a helper from `application/` would be the
    module's first inward import, which is the question PR 1.1a deliberately
    did not settle in a fake (`fake_historical_klines.py` records it).

    `ISymbolCatalogRepository` has always normalised this way on the way *in*
    (`JsonSymbolCatalogRepository.save_symbols`), so a cache hit was already
    normalised and a fresh exchange fetch was not: the same list came back in
    two shapes depending on whether it had been stored yet.
    """
    return tuple(
        sorted({s.strip().upper() for s in symbols if isinstance(s, str) and s.strip()})
    )


class ISymbolCatalog(ABC):
    """The symbols this context knows are open for trading."""

    @abstractmethod
    def list_symbols(self, *, force_refresh: bool = False) -> tuple[str, ...]:
        """Every tradeable symbol, upper-cased, de-duplicated and sorted.

        Normalised because three consumers render it straight into a picker,
        where `" btcusdt "` arriving twice is a visible defect — the same
        normalisation `ISymbolCatalogRepository` has always applied on the way
        in, now promised on the way out.

        Reads the stored catalog when it holds anything; fetches from the
        exchange when it is empty, or whenever `force_refresh=True`, and
        stores what it fetched. So a caller gets an answer without a network
        round trip in the ordinary case, and the refresh button is how a user
        asks for one deliberately.

        Empty rather than an error when the exchange has nothing to say. A
        *failure* to reach the exchange raises — both callers already catch it
        and show the user, because "we could not ask" is different from "there
        are none".
        """
