"""The two live tables of the trading account, as `RowTableModel`s.

**What this replaces.** `PositionsTable.qml` + `PositionRow.qml` and
`OpenOrdersTable.qml` + `OpenOrderRow.qml`: two hand-drawn tables, each a QML
`ListView` whose delegate painted every cell itself and, for open orders, put a
"Huỷ" button in every row. That is the shape ADR D20 rules out on the desktop —
a hand-drawn substitute for a component the platform already has
(`Docs/HLD/11_desktop_workbench.md`). PR 0.4b made the same move for the
Database Status table and this follows it deliberately rather than inventing a
second answer.

**Both models are here, in one file, on purpose.** They are the same
abstraction level with the same one reason to change — the shape of a row of
the account's order book (`code/quality.md` §3's Single-Scope Cohesion,
against `architecture-rule.md` §5's rule about abstraction *levels*, which is
not about count).

**Sorting is new, and had to be made correct.** Neither QML `ListView` had any.
`QSortFilterProxyModel` sorts on the role it is given, and `DisplayRole` here
is display *text*: `"-9.00 USDT"` sorts after `"+10.00 USDT"`, and `"1,000.00"`
before `"9.00"`. So each model serves `SORT_ROLE` with the comparable facts
behind the text, and the panels point their proxy at it.

**No colour.** The deleted delegates painted the PnL cell and the side label
from `Theme.success`/`Theme.danger` (`chart_card`'s `BULL_COLOR`/`BEAR_COLOR`).
ADR D21 leaves colour to the OS palette, and Qt has no palette role meaning
"this position is losing money", so the fact is carried where it cannot be
themed away: the sign is already in the text (`+10.00 USDT` / `-10.00 USDT`),
the side is a word (`LONG` / `SHORT`), and a losing row's PnL cell is **bold** —
the row the user came here to act on, which is the same emphasis and the same
argument `database_status_table_model.py` uses for a shard with gaps.

@par What left this file in PR 4.1b
`rowCount()`, `columnCount()`, `headerData()`, `row_for()`, `set_rows()` and the
first three branches of `data()` — every one of them byte-for-byte identical to
Data Management's two models, which neither pair could see because
`presentation/ui/components/` was never in the duplication metric's package set.
They are `support/ui_kit/table_model.py`'s now, together with `SORT_ROLE` and
`as_number()`, which this file had been carrying as second copies under a
comment that said the shared home was `support/ui_kit` "in Phase 4". What stays
is what is actually these two tables': their columns, their headers, which
columns are numeric, and the one bold cell.
"""

from __future__ import annotations

from typing import ClassVar, Final

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.open_order_row import (
    OpenOrderRow,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.position_row import (
    PositionRow,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.table_model import (
    RowTableModel,
    as_number,
)


def _bold() -> QFont:
    font = QFont()
    font.setBold(True)
    return font


class PositionsTableModel(RowTableModel[PositionRow]):
    """@brief Every position the account holds open, one per row."""

    SYMBOL_COLUMN: Final = 0
    SIDE_COLUMN: Final = 1
    SIZE_COLUMN: Final = 2
    ENTRY_COLUMN: Final = 3
    MARK_COLUMN: Final = 4
    PNL_COLUMN: Final = 5
    LEVERAGE_COLUMN: Final = 6
    LIQUIDATION_COLUMN: Final = 7

    HEADERS: ClassVar[tuple[str, ...]] = (
        "Symbol",
        "Side",
        "Size",
        "Entry",
        "Mark",
        "Unrealized PnL",
        "Leverage",
        "Liquidation",
    )

    #: Right-aligned because the eye compares a column of numbers by its last
    #: digit; symbol and side are text and stay left-aligned.
    RIGHT_ALIGNED: ClassVar[frozenset[int]] = frozenset(
        {SIZE_COLUMN, ENTRY_COLUMN, MARK_COLUMN, PNL_COLUMN, LIQUIDATION_COLUMN}
    )

    def _display_text(self, row: PositionRow, column: int) -> str:
        return {
            self.SYMBOL_COLUMN: row.symbol,
            self.SIDE_COLUMN: row.side.value.upper(),
            self.SIZE_COLUMN: row.quantity_text,
            self.ENTRY_COLUMN: row.entry_price_text,
            self.MARK_COLUMN: row.mark_price_text,
            self.PNL_COLUMN: row.unrealized_pnl_text,
            self.LEVERAGE_COLUMN: f"{row.leverage}x",
            self.LIQUIDATION_COLUMN: row.liquidation_price_text,
        }.get(column, "")

    def _sort_value(self, row: PositionRow, column: int) -> object:
        if column in {
            self.SIZE_COLUMN,
            self.ENTRY_COLUMN,
            self.MARK_COLUMN,
            self.PNL_COLUMN,
            self.LIQUIDATION_COLUMN,
        }:
            return as_number(self._display_text(row, column))
        if column == self.LEVERAGE_COLUMN:
            return row.leverage
        return self._display_text(row, column)

    def _role_data(self, row: PositionRow, column: int, role: int) -> object:
        """A losing position's PnL cell is bold. The one emphasis this table
        carries, and it replaces a colour (ADR D21)."""
        if (
            role == Qt.ItemDataRole.FontRole
            and column == self.PNL_COLUMN
            and not row.pnl_is_profit
        ):
            return _bold()
        return None


class OpenOrdersTableModel(RowTableModel[OpenOrderRow]):
    """@brief Every order the account has pending, one per row."""

    SYMBOL_COLUMN: Final = 0
    SIDE_COLUMN: Final = 1
    TYPE_COLUMN: Final = 2
    QUANTITY_COLUMN: Final = 3
    PRICE_COLUMN: Final = 4
    STATUS_COLUMN: Final = 5
    TIME_COLUMN: Final = 6

    HEADERS: ClassVar[tuple[str, ...]] = (
        "Symbol",
        "Side",
        "Type",
        "Quantity",
        "Price",
        "Status",
        "Order time",
    )

    RIGHT_ALIGNED: ClassVar[frozenset[int]] = frozenset({QUANTITY_COLUMN, PRICE_COLUMN})

    def _display_text(self, row: OpenOrderRow, column: int) -> str:
        return {
            self.SYMBOL_COLUMN: row.symbol,
            self.SIDE_COLUMN: row.side.value.upper(),
            self.TYPE_COLUMN: row.order_type_text,
            self.QUANTITY_COLUMN: row.quantity_text,
            self.PRICE_COLUMN: row.price_text,
            self.STATUS_COLUMN: row.status_text,
            self.TIME_COLUMN: row.order_time_text,
        }.get(column, "")

    def _sort_value(self, row: OpenOrderRow, column: int) -> object:
        if column in {self.QUANTITY_COLUMN, self.PRICE_COLUMN}:
            return as_number(self._display_text(row, column))
        return self._display_text(row, column)
