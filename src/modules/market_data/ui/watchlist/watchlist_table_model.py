"""The Watchlist table — one row per tracked symbol, updated live from
`MarketTickEvent` (`BOT-019`).

Colour on the `% Change` column is the one case
`ui-presentation-rule.md` §1 already sanctions ("colour only where it
carries meaning"): win/loss direction, the same `BULL_COLOR`/`BEAR_COLOR`
pair every other trade/tick direction in this codebase already uses (chart
markers, `dashboard_presenter.py`'s own WS status badge) — not a new
stylesheet or a decorative choice.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Final

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.theme import (
    BEAR_COLOR,
    BULL_COLOR,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.table_model import RowTableModel

_UNKNOWN_VALUE = "—"


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

    @property
    def is_bullish(self) -> bool | None:
        """`None` before any tick has been seen — there is nothing to
        colour yet, and painting one direction by default would claim
        knowledge this row does not have."""
        if self.percent_change is None:
            return None
        return self.percent_change >= 0.0


class WatchlistTableModel(RowTableModel[WatchlistRow]):
    """@brief Table model backing the Watchlist screen's symbol table."""

    SYMBOL_COLUMN: Final = 0
    LAST_PRICE_COLUMN: Final = 1
    PERCENT_CHANGE_COLUMN: Final = 2
    VOLUME_COLUMN: Final = 3

    HEADERS: ClassVar[tuple[str, ...]] = (
        "Symbol",
        "Last Price",
        "% Change",
        "Volume",
    )

    RIGHT_ALIGNED: ClassVar[frozenset[int]] = frozenset(
        {LAST_PRICE_COLUMN, PERCENT_CHANGE_COLUMN, VOLUME_COLUMN}
    )

    def __init__(self, parent=None) -> None:
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

    def _display_text(self, row: WatchlistRow, column: int) -> str:
        if column == self.SYMBOL_COLUMN:
            return row.symbol
        if column == self.LAST_PRICE_COLUMN:
            return (
                f"{row.last_price:,.2f}"
                if row.last_price is not None
                else _UNKNOWN_VALUE
            )
        if column == self.PERCENT_CHANGE_COLUMN:
            if row.percent_change is None:
                return _UNKNOWN_VALUE
            sign = "+" if row.percent_change >= 0.0 else ""
            return f"{sign}{row.percent_change:.2f}%"
        if column == self.VOLUME_COLUMN:
            return f"{row.volume:,.2f}" if row.volume is not None else _UNKNOWN_VALUE
        return ""

    def _sort_value(self, row: WatchlistRow, column: int) -> object:
        if column == self.LAST_PRICE_COLUMN:
            return row.last_price if row.last_price is not None else float("-inf")
        if column == self.PERCENT_CHANGE_COLUMN:
            return (
                row.percent_change if row.percent_change is not None else float("-inf")
            )
        if column == self.VOLUME_COLUMN:
            return row.volume if row.volume is not None else float("-inf")
        return self._display_text(row, column)

    def _role_data(self, row: WatchlistRow, column: int, role: int) -> object:
        if column != self.PERCENT_CHANGE_COLUMN:
            return None
        if role != Qt.ItemDataRole.ForegroundRole:
            return None
        if row.is_bullish is None:
            return None
        return QColor(BULL_COLOR if row.is_bullish else BEAR_COLOR)
