"""QML-facing wrapper around the real `DatabaseStatusTableModel`.

Structural pass only (user decision 2026-08-29, "dựng khung trước, đủ tính
năng sau"): rows render through the same model/roles a real screen's
`QTableView` already uses — not a second copy of that data — but search and
the row actions (KLines/Gaps/Sync/Clear) are not wired to anything yet.
`rowActionRequested` is a signal with no listener; it is the hook a future
host connects, not functionality built here.
"""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.database_status_table_model import (
    DatabaseStatusTableModel,
)


class DatabaseStatusVM(QObject):
    rowCountChanged = Signal()
    rowActionRequested = Signal(str, str, str)  # action, symbol, interval

    def __init__(
        self,
        model: DatabaseStatusTableModel,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._model.countsChanged.connect(self.rowCountChanged)

    @Property(QObject, constant=True)
    def rowsModel(self) -> DatabaseStatusTableModel:
        """The real model itself — QML binds `model: vm.rowsModel` directly,
        so a row's fields come straight from `DatabaseStatusTableModel`'s
        roles, not a second copy of the same data."""
        return self._model

    @Property(int, notify=rowCountChanged)
    def rowCount(self) -> int:
        return self._model.rowCount()

    @Slot(str, str, str)
    def requestAction(self, action: str, symbol: str, interval: str) -> None:
        self.rowActionRequested.emit(action, symbol, interval)
