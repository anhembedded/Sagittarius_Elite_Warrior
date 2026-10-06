"""Port: *what does this symbol's price move in, and its quantity?*
(`EPIC-033N`, per-symbol precision).

A price is quoted in its symbol's tick size and a quantity traded in its step
size, both the exchange's filters. A table knows the row's symbol; the
exchange filters live in a module's metadata cache. This port joins the two
without `support/ui_kit` importing a module: a table model asks it for the
`Precision` of one cell (the Engine's `PRECISION_ROLE`), and the formatter
writes the value with exactly the quantum's decimals.

`None` means the filters are not known yet (the catalog was never fetched, or
the venue does not list the symbol): the formatter then falls back to its
magnitude rule, so an unknown precision never blanks a cell.

Extension cases, each local (`architecture-rule.md` §7.2.1):
- another source of filters (a second exchange): one new implementation;
- a money column in a quote asset's smallest unit: one more method here;
- a precision that becomes known while shown (a catalog fetched later): the
  model is told to write its cells again (`RowTableModel.refresh_precisions`).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from sagittarius_engine.extensions.pyside_mvc.workbench import Precision


class ISymbolPrecisions(ABC):
    """A symbol's tick size and step size, as display precisions."""

    @abstractmethod
    def tick(self, symbol: str) -> Precision | None:
        """The quantum `symbol`'s prices are quoted in; `None` when unknown."""

    @abstractmethod
    def step(self, symbol: str) -> Precision | None:
        """The quantum `symbol`'s quantities are traded in; `None` when
        unknown."""
