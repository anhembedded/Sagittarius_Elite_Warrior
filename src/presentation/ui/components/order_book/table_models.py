"""The two live tables of the trading account, as `QAbstractTableModel`s.

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
the account's order book — and they share `SORT_ROLE` (`code-quality-rule.md`
§4's Single-Scope Cohesion, against `architecture-rule.md` §5's rule about
abstraction levels, which is about *levels*, not about count).

**Sorting is new, and had to be made correct.** Neither QML `ListView` had any.
`QSortFilterProxyModel` sorts on the role it is given, and `DisplayRole` here
is display *text*: `"-9.00 USDT"` sorts after `"+10.00 USDT"`, and `"1,000.00"`
before `"9.00"`. So each model also serves `SORT_ROLE`, whose values are the
comparable facts behind the text, and the panels point their proxy at it.

**No colour.** The deleted delegates painted the PnL cell and the side label
from `Theme.success`/`Theme.danger` (`chart_card`'s `BULL_COLOR`/`BEAR_COLOR`).
ADR D21 leaves colour to the OS palette, and Qt has no palette role meaning
"this position is losing money", so the fact is carried where it cannot be
themed away: the sign is already in the text (`+10.00 USDT` / `-10.00 USDT`),
the side is a word (`LONG` / `SHORT`), and a losing row's PnL cell is **bold** —
the row the user came here to act on, which is the same emphasis and the same
argument `database_status_table_model.py` uses for a shard with gaps.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import ClassVar, Final

from PySide6.QtCore import (
    QAbstractTableModel,
    QObject,
    Qt,
)
from PySide6.QtGui import QFont
from Sagittarius_Elite_Warrior.src.presentation.ui.components.order_book.open_order_row import (
    OpenOrderRow,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.order_book.position_row import (
    PositionRow,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.model_indexes import (
    AnyIndex,
)

#: The role carrying the comparable value behind a cell's display text, so a
#: numeric column sorts numerically. Defined per table family rather than
#: shared with `database_status_table_model.py`'s identical constant: a
#: component importing a screen is the cross-screen import the guards refuse,
#: and the shared home for both is `support/ui_kit` in Phase 4.
SORT_ROLE: Final = Qt.ItemDataRole.UserRole + 1


def _as_number(text: str) -> float:
    """The number a formatted cell means, for sorting. `"—"` — a value the
    exchange did not report — sorts below every real number rather than
    raising in the middle of a `sort()`."""
    try:
        return float(text.replace(",", "").replace(" ", "").replace("USDT", ""))
    except ValueError:
        return float("-inf")


def _bold() -> QFont:
    font = QFont()
    font.setBold(True)
    return font


class PositionsTableModel(QAbstractTableModel):
    """@brief Every position the account holds open, one per row."""

    SYMBOL_COLUMN: Final = 0
    SIDE_COLUMN: Final = 1
    SIZE_COLUMN: Final = 2
    ENTRY_COLUMN: Final = 3
    MARK_COLUMN: Final = 4
    PNL_COLUMN: Final = 5
    LEVERAGE_COLUMN: Final = 6
    LIQUIDATION_COLUMN: Final = 7

    _HEADERS: ClassVar[tuple[str, ...]] = (
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
    _RIGHT_ALIGNED: ClassVar[frozenset[int]] = frozenset(
        {SIZE_COLUMN, ENTRY_COLUMN, MARK_COLUMN, PNL_COLUMN, LIQUIDATION_COLUMN}
    )

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._rows: tuple[PositionRow, ...] = ()

    # -- QAbstractTableModel contract --------------------------------------

    def rowCount(self, parent: AnyIndex | None = None) -> int:
        if parent is not None and parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent: AnyIndex | None = None) -> int:
        if parent is not None and parent.isValid():
            return 0
        return len(self._HEADERS)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation != Qt.Orientation.Horizontal:
            return None
        if not 0 <= section < len(self._HEADERS):
            return None
        return self._HEADERS[section]

    def data(self, index: AnyIndex, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        row = self.row_for(index)
        if row is None:
            return None
        column = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            return self._display_text(row, column)
        if role == SORT_ROLE:
            return self._sort_value(row, column)
        if role == Qt.ItemDataRole.TextAlignmentRole and column in self._RIGHT_ALIGNED:
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if (
            role == Qt.ItemDataRole.FontRole
            and column == self.PNL_COLUMN
            and not row.pnl_is_profit
        ):
            return _bold()
        return None

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
            return _as_number(self._display_text(row, column))
        if column == self.LEVERAGE_COLUMN:
            return row.leverage
        return self._display_text(row, column)

    # -- reading and writing whole rows ------------------------------------

    def row_for(self, index: AnyIndex) -> PositionRow | None:
        """The row behind an index, or `None` when the index is stale.

        A typed accessor rather than a `Qt.UserRole` payload, same reasoning
        `database_status_table_model.py` records: a caller wanting the row
        wants the whole row, and `data(index, SomeRole)` returning `object`
        would make every one of them cast.
        """
        if not index.isValid():
            return None
        if not 0 <= index.row() < len(self._rows):
            return None
        return self._rows[index.row()]

    def set_rows(self, rows: Sequence[PositionRow]) -> None:
        """Replaces every row. The full set arrives on each update — the feed
        that drives this holds the whole order book (`EPIC-021H`) — so a reset
        is the honest model operation, not a diff nobody computed."""
        self.beginResetModel()
        self._rows = tuple(rows)
        self.endResetModel()


class OpenOrdersTableModel(QAbstractTableModel):
    """@brief Every order the account has pending, one per row."""

    SYMBOL_COLUMN: Final = 0
    SIDE_COLUMN: Final = 1
    TYPE_COLUMN: Final = 2
    QUANTITY_COLUMN: Final = 3
    PRICE_COLUMN: Final = 4
    STATUS_COLUMN: Final = 5
    TIME_COLUMN: Final = 6

    _HEADERS: ClassVar[tuple[str, ...]] = (
        "Symbol",
        "Side",
        "Type",
        "Quantity",
        "Price",
        "Status",
        "Order time",
    )

    _RIGHT_ALIGNED: ClassVar[frozenset[int]] = frozenset(
        {QUANTITY_COLUMN, PRICE_COLUMN}
    )

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._rows: tuple[OpenOrderRow, ...] = ()

    # -- QAbstractTableModel contract --------------------------------------

    def rowCount(self, parent: AnyIndex | None = None) -> int:
        if parent is not None and parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent: AnyIndex | None = None) -> int:
        if parent is not None and parent.isValid():
            return 0
        return len(self._HEADERS)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation != Qt.Orientation.Horizontal:
            return None
        if not 0 <= section < len(self._HEADERS):
            return None
        return self._HEADERS[section]

    def data(self, index: AnyIndex, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        row = self.row_for(index)
        if row is None:
            return None
        column = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            return self._display_text(row, column)
        if role == SORT_ROLE:
            return self._sort_value(row, column)
        if role == Qt.ItemDataRole.TextAlignmentRole and column in self._RIGHT_ALIGNED:
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return None

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
            return _as_number(self._display_text(row, column))
        return self._display_text(row, column)

    # -- reading and writing whole rows ------------------------------------

    def row_for(self, index: AnyIndex) -> OpenOrderRow | None:
        if not index.isValid():
            return None
        if not 0 <= index.row() < len(self._rows):
            return None
        return self._rows[index.row()]

    def set_rows(self, rows: Sequence[OpenOrderRow]) -> None:
        self.beginResetModel()
        self._rows = tuple(rows)
        self.endResetModel()
