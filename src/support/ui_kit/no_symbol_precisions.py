"""`NoSymbolPrecisions` — the `ISymbolPrecisions` of a table that knows no
exchange filters: every cell falls back to the formatter's magnitude rule.

The default of every `RowTableModel`, so a table that is never given filters
(a preview, a table whose rows carry no symbol) writes exactly what it wrote
before per-symbol precision existed.
"""

from __future__ import annotations

from typing import Final

from Sagittarius_Elite_Warrior.src.support.ui_kit.i_symbol_precisions import (
    ISymbolPrecisions,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import Precision


class NoSymbolPrecisions(ISymbolPrecisions):
    """Knows no symbol's filters."""

    def tick(self, symbol: str) -> Precision | None:
        return None

    def step(self, symbol: str) -> Precision | None:
        return None


#: The one instance; it holds no state.
NO_SYMBOL_PRECISIONS: Final = NoSymbolPrecisions()
