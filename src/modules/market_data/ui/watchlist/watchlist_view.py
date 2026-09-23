"""The Watchlist screen (`BOT-019`) — a live `QTableView` of tracked symbols,
replacing the need to open a `ChartCard` per symbol just to see its current
price, % change and volume.
"""

from __future__ import annotations

from PySide6.QtCore import QSortFilterProxyModel, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTableView,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit.page_shell import PageShell
from Sagittarius_Elite_Warrior.src.support.ui_kit.table_model import SORT_ROLE
from sagittarius_engine.extensions.pyside_mvc import BaseView

from .watchlist_table_model import WatchlistTableModel


class WatchlistView(BaseView):
    """@brief The Watchlist screen — a table of tracked symbols, updated live."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.model = WatchlistTableModel(self)
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self.model)
        self._proxy.setSortRole(SORT_ROLE)

        self.table = self._build_table()

        shell = PageShell()
        shell.set_header(
            "Watchlist", "Live price, % change and volume for tracked symbols"
        )
        shell.set_workspace(self.table)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(shell)

    def _build_table(self) -> QTableView:
        table = QTableView()
        table.setObjectName("tblWatchlist")
        table.setModel(self._proxy)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.setWordWrap(False)
        table.setSortingEnabled(True)
        table.sortByColumn(
            WatchlistTableModel.SYMBOL_COLUMN, Qt.SortOrder.AscendingOrder
        )
        table.verticalHeader().setVisible(False)
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(
            WatchlistTableModel.SYMBOL_COLUMN, QHeaderView.ResizeMode.Stretch
        )
        return table
