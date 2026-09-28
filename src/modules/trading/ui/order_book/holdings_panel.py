"""The Holdings panel — a `QTableView` over every Spot asset the account
holds (`EPIC-027O`).

@details Mirrors `positions_panel.py` file-for-file: read-only (a holding
changes by placing an order, not by acting on a row), no toolbar, a stacked
empty state so an account holding nothing does not look like a table that
never loaded.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QSortFilterProxyModel, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QStackedWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.holding_row import (
    HoldingRow,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.table_models import (
    HoldingsTableModel,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.table_model import SORT_ROLE

_EMPTY_TEXT = "No holdings."


class HoldingsPanel(QWidget):  # base-exempt: a container, not a surface
    """@brief The account's Spot holdings, as the platform's own table."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._model = HoldingsTableModel(self)
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)
        self._proxy.setSortRole(SORT_ROLE)

        self._table = QTableView()
        self._table.setObjectName("tblHoldings")
        self._table.setModel(self._proxy)
        self._table.setSortingEnabled(True)
        # Same reasoning `positions_panel.py` gives for its own explicit
        # initial sort: asset ascending is the stable order a reader can
        # find a holding in.
        self._table.sortByColumn(
            HoldingsTableModel.ASSET_COLUMN, Qt.SortOrder.AscendingOrder
        )
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(
            HoldingsTableModel.ASSET_COLUMN, QHeaderView.ResizeMode.ResizeToContents
        )

        self._empty = QLabel(_EMPTY_TEXT)
        self._empty.setObjectName("lblHoldingsEmpty")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setWordWrap(True)

        self._body = QStackedWidget()
        self._body.setObjectName("stkHoldingsBody")
        self._body.addWidget(self._empty)
        self._body.addWidget(self._table)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._body)
        self._show_body()

    def set_rows(self, rows: Sequence[HoldingRow]) -> None:
        """Replaces the table's rows entirely — the feed driving this holds
        the whole set (`HoldingsChangedEvent`'s own docstring)."""
        self._model.set_rows(rows)
        self._show_body()

    @property
    def table(self) -> QTableView:
        """For a host that needs to size or focus the table itself."""
        return self._table

    def _show_body(self) -> None:
        self._body.setCurrentWidget(
            self._table if self._model.rowCount() else self._empty
        )
