"""The Backtest mode's Trades table (`EPIC-033L`): one row per finished trade
that matches the filter and the search, built from its column specs like
every table of the application (`EPIC-033N`).

The profit and the return carry colour as well as their sign: gain in the
bull colour, loss in the bear colour, the sign saying the same in text
(`ui-presentation-rule.md` §1).
"""

from __future__ import annotations

from typing import ClassVar

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.theme import (
    BEAR_COLOR,
    BULL_COLOR,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.table_model import RowTableModel
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ColumnKind,
    ColumnSpec,
    DisplayValue,
)

from .logic.trade_log_row import TradeLogRow

#: The two columns whose value is a gain or a loss.
_SIGNED_KEYS = frozenset({"pnl", "return"})


class TradeTableModel(RowTableModel[TradeLogRow]):
    """The trades of the run on screen."""

    COLUMNS: ClassVar[tuple[ColumnSpec, ...]] = (
        ColumnSpec("number", "#", ColumnKind.QUANTITY),
        ColumnSpec("side", "Side", ColumnKind.SIDE),
        ColumnSpec("entry_time", "Entry time", ColumnKind.TIMESTAMP),
        ColumnSpec("entry_price", "Entry price", ColumnKind.PRICE),
        ColumnSpec("exit_time", "Exit time", ColumnKind.TIMESTAMP),
        ColumnSpec("exit_price", "Exit price", ColumnKind.PRICE),
        ColumnSpec("quantity", "Quantity", ColumnKind.QUANTITY),
        ColumnSpec("size", "Size", ColumnKind.MONEY),
        ColumnSpec("pnl", "Net profit", ColumnKind.MONEY),
        ColumnSpec("return", "Return", ColumnKind.PERCENT, stretch=True),
    )

    def _value(self, row: TradeLogRow, column: int) -> DisplayValue:
        values: tuple[DisplayValue, ...] = (
            row.index,
            row.side.value.upper(),
            row.entry_time,
            row.entry_price,
            row.exit_time,
            row.exit_price,
            row.quantity,
            row.quantity * row.entry_price,
            row.pnl,
            row.pnl_percent,
        )
        return values[column]

    def _role_data(self, row: TradeLogRow, column: int, role: int) -> object:
        if role != Qt.ItemDataRole.ForegroundRole:
            return None
        if self.COLUMNS[column].key not in _SIGNED_KEYS:
            return None
        return QColor(BULL_COLOR if row.pnl >= 0 else BEAR_COLOR)
