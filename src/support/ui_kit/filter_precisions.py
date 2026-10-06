"""`FilterPrecisions` — a venue's tick and step sizes, from the order metadata
it has already read, as the precisions a table writes prices and quantities
in (`EPIC-033N`).

It reads a cache of one venue's symbol filters and never the network: a
table asks on the UI thread, on every paint. The trading module's
`ISymbolOrderMetadataCache` is that cache; it fills when something first
reads a symbol's order terms (a desk's order panel, a Grid's planner), which
fetches the venue's whole catalog. Until then every symbol is unknown and its
cells keep the formatter's magnitude rule. A stale entry still answers: a
tick size changes rarely, and the order path re-reads it before an order is
shaped.

@par Why it lives in `support/ui_kit`
Two modules write a venue's filters into their tables: trading (the desk's
account tabs) and bots (a bot's orders and fills). `support/ui_kit` imports
no module, so the cache is described here by the two members a table needs.

@par Why `SymbolFilterSource` and `SymbolFilters` are Protocols
`architecture-rule.md` §2's reason (b), a second base the rules forbid. The
cache's implementers (`InMemorySymbolOrderMetadataCache`, the testing
`UnarrangedMetadataCache`) already derive from trading's
`ISymbolOrderMetadataCache`, and §2 allows no second base. The filters'
implementer, `SymbolOrderMetadata`, is a trading contract, and a contract
imports only the shared kernel
(`test_module_inside_imports_only_the_shared_kernel.py`), so it cannot derive
from a class here.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol, runtime_checkable

from Sagittarius_Elite_Warrior.src.support.ui_kit.i_symbol_precisions import (
    ISymbolPrecisions,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import Precision


@runtime_checkable
class SymbolFilters(Protocol):
    """One symbol's price and quantity filters, as an exchange states them."""

    @property
    def tick_size(self) -> Decimal: ...

    @property
    def step_size(self) -> Decimal: ...


@runtime_checkable
class SymbolFilterSource(Protocol):
    """One venue's cached filters: a symbol's, or `None` while unknown."""

    def get(self, symbol: str) -> SymbolFilters | None: ...


def precision_of(quantum: Decimal | float) -> Precision | None:
    """A filter's size as a `Precision`; `None` for a size of zero, which is
    Binance's "this filter does not restrict" and says nothing of decimals."""
    exact = quantum if isinstance(quantum, Decimal) else Decimal(repr(quantum))
    if not exact.is_finite() or exact <= 0:
        return None
    return Precision(exact)


class FilterPrecisions(ISymbolPrecisions):
    """One venue's cached filters, as display precisions."""

    def __init__(self, filters: SymbolFilterSource) -> None:
        self._filters = filters

    def tick(self, symbol: str) -> Precision | None:
        filters = self._filters.get(symbol)
        return None if filters is None else precision_of(filters.tick_size)

    def step(self, symbol: str) -> Precision | None:
        filters = self._filters.get(symbol)
        return None if filters is None else precision_of(filters.step_size)
