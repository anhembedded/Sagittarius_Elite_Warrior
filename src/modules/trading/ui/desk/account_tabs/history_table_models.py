"""`EPIC-028J` — the Order history and Trade history tables, as
`RowTableModel`s.

@details Both in one file for the reason `order_book/table_models.py` gives
for its three: the same abstraction level and the same one reason to change,
the shape of a row of the account's history. Numeric columns serve
`SORT_ROLE` with the number behind the text, so "1,000.00" sorts after
"9.00".
"""

from __future__ import annotations

from typing import ClassVar, Final

from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_tabs.history_rows import (
    OrderHistoryRow,
    TradeHistoryRow,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.table_model import (
    RowTableModel,
    as_number,
)


class OrderHistoryTableModel(RowTableModel[OrderHistoryRow]):
    """@brief One page of the account's orders, one per row."""

    TIME_COLUMN: Final = 0
    SYMBOL_COLUMN: Final = 1
    SIDE_COLUMN: Final = 2
    TYPE_COLUMN: Final = 3
    PRICE_COLUMN: Final = 4
    STOP_COLUMN: Final = 5
    AVERAGE_COLUMN: Final = 6
    QUANTITY_COLUMN: Final = 7
    FILLED_COLUMN: Final = 8
    STATUS_COLUMN: Final = 9

    HEADERS: ClassVar[tuple[str, ...]] = (
        "Created",
        "Symbol",
        "Side",
        "Type",
        "Price",
        "Stop",
        "Average",
        "Quantity",
        "Filled",
        "Status",
    )

    RIGHT_ALIGNED: ClassVar[frozenset[int]] = frozenset(
        {PRICE_COLUMN, STOP_COLUMN, AVERAGE_COLUMN, QUANTITY_COLUMN, FILLED_COLUMN}
    )

    def _display_text(self, row: OrderHistoryRow, column: int) -> str:
        return {
            self.TIME_COLUMN: row.created_text,
            self.SYMBOL_COLUMN: row.symbol,
            self.SIDE_COLUMN: row.side.value.upper(),
            self.TYPE_COLUMN: row.order_type_text,
            self.PRICE_COLUMN: row.price_text,
            self.STOP_COLUMN: row.stop_price_text,
            self.AVERAGE_COLUMN: row.average_price_text,
            self.QUANTITY_COLUMN: row.quantity_text,
            self.FILLED_COLUMN: row.filled_text,
            self.STATUS_COLUMN: row.status_text,
        }.get(column, "")

    def _sort_value(self, row: OrderHistoryRow, column: int) -> object:
        if column in self.RIGHT_ALIGNED:
            return as_number(self._display_text(row, column))
        return self._display_text(row, column)


class TradeHistoryTableModel(RowTableModel[TradeHistoryRow]):
    """@brief One page of the account's fills, one per row."""

    TIME_COLUMN: Final = 0
    SYMBOL_COLUMN: Final = 1
    SIDE_COLUMN: Final = 2
    PRICE_COLUMN: Final = 3
    QUANTITY_COLUMN: Final = 4
    QUOTE_COLUMN: Final = 5
    FEE_COLUMN: Final = 6
    PNL_COLUMN: Final = 7

    HEADERS: ClassVar[tuple[str, ...]] = (
        "Time",
        "Symbol",
        "Side",
        "Price",
        "Quantity",
        "Total",
        "Fee",
        "Realized PnL",
    )

    RIGHT_ALIGNED: ClassVar[frozenset[int]] = frozenset(
        {PRICE_COLUMN, QUANTITY_COLUMN, QUOTE_COLUMN, FEE_COLUMN, PNL_COLUMN}
    )

    def _display_text(self, row: TradeHistoryRow, column: int) -> str:
        return {
            self.TIME_COLUMN: row.time_text,
            self.SYMBOL_COLUMN: row.symbol,
            self.SIDE_COLUMN: row.side.value.upper(),
            self.PRICE_COLUMN: row.price_text,
            self.QUANTITY_COLUMN: row.quantity_text,
            self.QUOTE_COLUMN: row.quote_quantity_text,
            self.FEE_COLUMN: row.fee_text,
            self.PNL_COLUMN: row.realized_pnl_text,
        }.get(column, "")

    def _sort_value(self, row: TradeHistoryRow, column: int) -> object:
        if column == self.FEE_COLUMN:
            # The figure without its asset: "0.10 USDT" and "0.0002 BNB"
            # are not one currency, but a reader sorts to find the large one.
            return as_number(row.fee_text.split(" ")[0])
        if column in self.RIGHT_ALIGNED:
            return as_number(self._display_text(row, column))
        return self._display_text(row, column)
