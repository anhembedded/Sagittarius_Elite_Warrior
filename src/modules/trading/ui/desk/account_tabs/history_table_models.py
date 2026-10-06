"""`EPIC-028J` — the Order history and Trade history tables, as
`RowTableModel`s.

@details Both in one file for the reason `order_book/table_models.py` gives
for its three: the same abstraction level and the same one reason to change,
the shape of a row of the account's history. Columns are specs and cells
raw values (`EPIC-033N`), so "1,000.00" sorts after "9.00" because both are
numbers. A price or a size is written in its symbol's tick or step
(`SYMBOL_QUOTED`); a fee is a quantity of its own asset and is not.
"""

from __future__ import annotations

from typing import ClassVar

from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_tabs.history_rows import (
    OrderHistoryRow,
    TradeHistoryRow,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.table_model import RowTableModel
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ColumnKind,
    ColumnSpec,
    DisplayValue,
)


class OrderHistoryTableModel(RowTableModel[OrderHistoryRow]):
    """@brief One page of the account's orders, one per row."""

    COLUMNS: ClassVar[tuple[ColumnSpec, ...]] = (
        ColumnSpec("created", "Created", ColumnKind.TIMESTAMP),
        ColumnSpec("symbol", "Symbol", ColumnKind.TEXT, stretch=True),
        ColumnSpec("side", "Side", ColumnKind.SIDE),
        ColumnSpec("type", "Type", ColumnKind.TEXT),
        ColumnSpec("price", "Price", ColumnKind.PRICE),
        ColumnSpec("stop", "Stop", ColumnKind.PRICE),
        ColumnSpec("average", "Average", ColumnKind.PRICE),
        ColumnSpec("quantity", "Quantity", ColumnKind.QUANTITY),
        ColumnSpec("filled", "Filled", ColumnKind.QUANTITY),
        ColumnSpec("status", "Status", ColumnKind.STATUS),
    )
    SYMBOL_QUOTED: ClassVar[frozenset[str]] = frozenset(
        {"price", "stop", "average", "quantity", "filled"}
    )

    def _value(self, row: OrderHistoryRow, column: int) -> DisplayValue:
        values: tuple[DisplayValue, ...] = (
            row.created,
            row.symbol,
            row.side.value.upper(),
            row.order_type,
            row.price,
            row.stop_price,
            row.average_price,
            row.quantity,
            row.filled,
            row.status,
        )
        return values[column]

    def _symbol(self, row: OrderHistoryRow) -> str | None:
        return row.symbol


class TradeHistoryTableModel(RowTableModel[TradeHistoryRow]):
    """@brief One page of the account's fills, one per row."""

    COLUMNS: ClassVar[tuple[ColumnSpec, ...]] = (
        ColumnSpec("time", "Time", ColumnKind.TIMESTAMP),
        ColumnSpec("symbol", "Symbol", ColumnKind.TEXT, stretch=True),
        ColumnSpec("side", "Side", ColumnKind.SIDE),
        ColumnSpec("price", "Price", ColumnKind.PRICE),
        ColumnSpec("quantity", "Quantity", ColumnKind.QUANTITY),
        ColumnSpec("total", "Total", ColumnKind.MONEY),
        ColumnSpec("fee", "Fee", ColumnKind.QUANTITY),
        ColumnSpec("fee_asset", "Fee asset", ColumnKind.TEXT),
        ColumnSpec("pnl", "Realized PnL", ColumnKind.MONEY),
    )
    #: The fee is a quantity of its own asset, not of the symbol.
    SYMBOL_QUOTED: ClassVar[frozenset[str]] = frozenset({"price", "quantity"})

    def _value(self, row: TradeHistoryRow, column: int) -> DisplayValue:
        values: tuple[DisplayValue, ...] = (
            row.time,
            row.symbol,
            row.side.value.upper(),
            row.price,
            row.quantity,
            row.quote_quantity,
            row.fee,
            row.fee_asset,
            row.realized_pnl,
        )
        return values[column]

    def _symbol(self, row: TradeHistoryRow) -> str | None:
        return row.symbol
