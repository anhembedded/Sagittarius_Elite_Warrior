"""The verified fake for `ISymbolCatalogRepository` (HLD §10.3).

**This is public API.** It ships with the port, inside the provider module, so a
consumer testing against market_data's symbol catalog imports *this* instead of
writing its own substitute. `Mock(spec=ISymbolCatalogRepository)` is exactly
what `BUG-026` and `BUG-027` were: hand-written stand-ins that drifted from the
real port and kept passing while production was broken. A `Mock` cannot drift
*into* a failure — it agrees with whatever the test asserts.

What makes it a *verified* fake rather than just an in-memory one:
`contract_symbol_catalog.py` states the port's guarantees once, and both this
and `JsonSymbolCatalogRepository` run that same suite — the fake in unit, the
real in integration. If this fake ever answers differently from the real one on
a guarantee any consumer relies on, the same test fails for one of them.

It lives in `src/` rather than `tests/` deliberately: `tests/` is not importable
API for another module's test, and a fake nobody outside the provider can import
is a fake every consumer will re-invent.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_symbol_catalog_repository import (
    ISymbolCatalogRepository,
)


def _normalised(symbols: list[str]) -> list[str]:
    """Upper-cased, trimmed, de-duplicated, sorted — the port's stored form.

    Not an implementation detail of either side: three UI consumers read this
    list straight into a picker, so "BTCUSDT" arriving as `" btcusdt "`, twice,
    is a visible defect. `JsonSymbolCatalogRepository.save_symbols()` has always
    normalised this way; until the contract suite said so, nothing stopped a
    second implementation from skipping it.
    """
    return sorted(
        {s.strip().upper() for s in symbols if isinstance(s, str) and s.strip()}
    )


class FakeSymbolCatalog(ISymbolCatalogRepository):
    """The symbol catalog, in a list, with the real one's normalisation."""

    def __init__(self, symbols: list[str] | None = None) -> None:
        """`symbols` seeds the catalog as if a previous run had saved them, so a
        consumer's test starts from the state it needs in one line."""
        self._symbols: list[str] = _normalised(symbols or [])

    def get_symbols(self) -> list[str]:
        # A copy, not the list itself: the real one reads a file, so a caller
        # that mutates the result cannot corrupt the store. A fake that handed
        # out its own list would let a consumer's test pass on behaviour the
        # real implementation does not have.
        return list(self._symbols)

    def save_symbols(self, symbols: list[str]) -> None:
        self._symbols = _normalised(symbols)
