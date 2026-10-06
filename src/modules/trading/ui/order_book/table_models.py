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

**Prices and sizes in the symbol's own tick and step (`EPIC-033N`).**
Each model names the columns quoted in its row's symbol (`SYMBOL_QUOTED`);
the desk gives the tables its venue's filters
(`OrderMetadataPrecisions`). Holdings name an asset, not a symbol, so they
keep the magnitude rule.

**Columns are specs (`EPIC-033N`).** Each model declares its `COLUMNS` — key,
title, kind — and serves raw values; the Engine's `configure_item_view`
aligns, sorts and writes them by kind. Sorting is numeric because the value
is a number, not because a `SORT_ROLE` stood beside the text, which is what
this file carried until then.

**No colour.** The deleted delegates painted the PnL cell and the side label
from `Theme.success`/`Theme.danger` (`chart_card`'s `BULL_COLOR`/`BEAR_COLOR`).
ADR D21 leaves colour to the OS palette, and Qt has no palette role meaning
"this position is losing money", so the fact is carried where it cannot be
themed away: the sign is already in the number (`10.00` / `-10.00`),
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
is what is actually these tables': their columns and the one bold cell.
"""

from __future__ import annotations

from typing import ClassVar

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.holding_row import (
    HoldingRow,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.open_order_row import (
    OpenOrderRow,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.position_row import (
    PositionRow,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.table_model import RowTableModel
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import (
    display_number,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ColumnKind,
    ColumnSpec,
    DisplayValue,
)


def _bold() -> QFont:
    font = QFont()
    font.setBold(True)
    return font


class PositionsTableModel(RowTableModel[PositionRow]):
    """@brief Every position the account holds open, one per row."""

    COLUMNS: ClassVar[tuple[ColumnSpec, ...]] = (
        ColumnSpec("symbol", "Symbol", ColumnKind.TEXT, stretch=True),
        ColumnSpec("side", "Side", ColumnKind.SIDE),
        ColumnSpec("size", "Size", ColumnKind.QUANTITY),
        ColumnSpec("entry", "Entry", ColumnKind.PRICE),
        ColumnSpec("mark", "Mark", ColumnKind.PRICE),
        ColumnSpec("pnl", "Unrealized PnL (USDT)", ColumnKind.MONEY),
        ColumnSpec("leverage", "Leverage (x)", ColumnKind.QUANTITY),
        ColumnSpec("liquidation", "Liquidation", ColumnKind.PRICE),
    )
    #: The leverage is a quantity, but not of the symbol.
    SYMBOL_QUOTED: ClassVar[frozenset[str]] = frozenset(
        {"size", "entry", "mark", "liquidation"}
    )

    def _value(self, row: PositionRow, column: int) -> DisplayValue:
        values: tuple[DisplayValue, ...] = (
            row.symbol,
            row.side.value.upper(),
            display_number(row.quantity),
            display_number(row.entry_price),
            display_number(row.mark_price),
            display_number(row.unrealized_pnl),
            row.leverage,
            display_number(row.liquidation_price),
        )
        return values[column]

    def _symbol(self, row: PositionRow) -> str | None:
        return row.symbol

    def _role_data(self, row: PositionRow, column: int, role: int) -> object:
        """A losing position's PnL cell is bold. The one emphasis this table
        carries, and it replaces a colour (ADR D21)."""
        if (
            role == Qt.ItemDataRole.FontRole
            and column == self.column("pnl")
            and not row.pnl_is_profit
        ):
            return _bold()
        return None


class OpenOrdersTableModel(RowTableModel[OpenOrderRow]):
    """@brief Every order the account has pending, one per row."""

    COLUMNS: ClassVar[tuple[ColumnSpec, ...]] = (
        ColumnSpec("symbol", "Symbol", ColumnKind.TEXT, stretch=True),
        ColumnSpec("side", "Side", ColumnKind.SIDE),
        ColumnSpec("type", "Type", ColumnKind.TEXT),
        ColumnSpec("quantity", "Quantity", ColumnKind.QUANTITY),
        ColumnSpec("price", "Price", ColumnKind.PRICE),
        ColumnSpec("status", "Status", ColumnKind.STATUS),
        ColumnSpec("time", "Order time", ColumnKind.TIMESTAMP),
    )
    SYMBOL_QUOTED: ClassVar[frozenset[str]] = frozenset({"quantity", "price"})

    def _value(self, row: OpenOrderRow, column: int) -> DisplayValue:
        values: tuple[DisplayValue, ...] = (
            row.symbol,
            row.side.value.upper(),
            row.order_type,
            display_number(row.quantity),
            display_number(row.price),
            row.status,
            row.order_time,
        )
        return values[column]

    def _symbol(self, row: OpenOrderRow) -> str | None:
        return row.symbol


class HoldingsTableModel(RowTableModel[HoldingRow]):
    """@brief Every Spot asset the account holds, one per row (`EPIC-027O`).

    @details The Spot-venue counterpart to `PositionsTableModel` — same
    file, same abstraction level and the same one reason to change (the
    shape of a row of the account's order book), per this file's own
    docstring on why both existing models already live together here.
    """

    COLUMNS: ClassVar[tuple[ColumnSpec, ...]] = (
        ColumnSpec("asset", "Asset", ColumnKind.TEXT, stretch=True),
        ColumnSpec("free", "Free", ColumnKind.QUANTITY),
        ColumnSpec("locked", "Locked", ColumnKind.QUANTITY),
        ColumnSpec("value", "Value (USDT)", ColumnKind.MONEY),
    )

    def _value(self, row: HoldingRow, column: int) -> DisplayValue:
        values: tuple[DisplayValue, ...] = (
            row.asset,
            display_number(row.free),
            display_number(row.locked),
            display_number(row.value),
        )
        return values[column]
