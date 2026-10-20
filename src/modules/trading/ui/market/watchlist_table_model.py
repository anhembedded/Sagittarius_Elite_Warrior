"""The Watchlist table — one row per tracked symbol, updated live from
`MarketTickEvent` (`BOT-019`).

Colour on the `% Change` column is the one case
`ui-presentation-rule.md` §1 already sanctions ("colour only where it
carries meaning"): win/loss direction, drawn by `Tone` on the application's
palette (`EPIC-043C`) with an arrow and a sign beside it in the text; a
change of exactly zero has neither colour nor arrow.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import ClassVar, Final

from PySide6.QtCore import QObject
from Sagittarius_Elite_Warrior.src.support.ui_kit.meaning_colours import (
    Tone,
    sign_tone,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.table_model import RowTableModel
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import signed_key
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ColumnKind,
    ColumnSpec,
    DisplayValue,
)


@dataclass
class WatchlistRow:
    """One tracked symbol's latest known price/change/volume.

    Every field beyond `symbol` is `None` until the first tick for that
    symbol arrives — a symbol is seeded into the table the moment the
    watchlist starts tracking it (`WatchlistTableModel.set_symbols()`), so
    the user sees the full list immediately rather than an empty table
    until ticks start flowing.
    """

    symbol: str
    last_price: float | None = None
    percent_change: float | None = None
    volume: float | None = None


class WatchlistTableModel(RowTableModel[WatchlistRow]):
    """@brief Table model backing the Watchlist screen's symbol table."""

    SYMBOL_COLUMN: Final = 0
    PERCENT_CHANGE_COLUMN: Final = 2

    COLUMNS: ClassVar[tuple[ColumnSpec, ...]] = (
        ColumnSpec("symbol", "Symbol", ColumnKind.TEXT, stretch=True),
        ColumnSpec("last_price", "Last price", ColumnKind.PRICE),
        ColumnSpec(signed_key("change"), "% Change", ColumnKind.PERCENT),
        ColumnSpec("volume", "Volume", ColumnKind.QUANTITY),
    )
    #: A volume is a sum of the symbol's traded quantities, so its step.
    SYMBOL_QUOTED: ClassVar[frozenset[str]] = frozenset({"last_price", "volume"})

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._row_index: dict[str, int] = {}

    # ------------------------------------------------------------------ #
    # Mutation API (driven by the Presenter)
    # ------------------------------------------------------------------ #

    def set_symbols(self, symbols: list[str]) -> None:
        """Replaces the tracked symbol list, one blank row per symbol.

        Called once at startup (and again if Settings' `DEFAULT_SYMBOLS`
        changes the tracked list) — never per tick, which is what
        `update_tick()` is for.
        """
        self.set_rows([WatchlistRow(symbol=symbol) for symbol in symbols])
        self._row_index = {row.symbol: index for index, row in enumerate(self._rows)}

    def track(self, symbols: Sequence[str]) -> None:
        """Tracks `symbols`, in that order: a symbol already listed keeps its
        latest price, change and volume, a new one starts blank
        (`EPIC-033V`), where `set_symbols` blanks them all."""
        known = {row.symbol: row for row in self._rows}
        self.set_rows([known.get(symbol) or WatchlistRow(symbol) for symbol in symbols])
        self._row_index = {row.symbol: index for index, row in enumerate(self._rows)}

    def update_tick(
        self,
        symbol: str,
        last_price: float,
        percent_change: float,
        volume: float,
    ) -> None:
        """Updates one symbol's row in place, keeping the user's selection
        and scroll position — a tick for a symbol this watchlist is not
        tracking (`set_symbols()` was never called with it) is ignored."""
        index = self._row_index.get(symbol)
        if index is None:
            return
        self._rows[index] = WatchlistRow(
            symbol=symbol,
            last_price=last_price,
            percent_change=percent_change,
            volume=volume,
        )
        self.dataChanged.emit(
            self.index(index, 0), self.index(index, self.columnCount() - 1)
        )

    # -- what this table decides (the rest is `RowTableModel`'s) -----------

    def _value(self, row: WatchlistRow, column: int) -> DisplayValue:
        values: tuple[DisplayValue, ...] = (
            row.symbol,
            row.last_price,
            row.percent_change,
            row.volume,
        )
        return values[column]

    def _symbol(self, row: WatchlistRow) -> str | None:
        return row.symbol

    def _tone(self, row: WatchlistRow, column: int) -> Tone:
        """No tone before any tick has been seen: painting one direction by
        default would claim knowledge this row does not have."""
        if column != self.PERCENT_CHANGE_COLUMN:
            return Tone.NEUTRAL
        return sign_tone(row.percent_change)
