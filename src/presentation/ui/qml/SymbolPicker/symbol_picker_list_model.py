"""Qt list model used by the standalone SymbolPicker views."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import ClassVar

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt

_INVALID_INDEX = QModelIndex()


class SymbolListModel(QAbstractListModel):
    """Expose symbol rows through named Qt roles for virtualized QML views."""

    SYMBOL_ROLE = Qt.ItemDataRole.UserRole + 1
    BASE_ROLE = Qt.ItemDataRole.UserRole + 2
    QUOTE_ROLE = Qt.ItemDataRole.UserRole + 3
    SUBTITLE_ROLE = Qt.ItemDataRole.UserRole + 4
    FAVOURITE_ROLE = Qt.ItemDataRole.UserRole + 5
    CURRENT_ROLE = Qt.ItemDataRole.UserRole + 6
    FOCUSED_ROLE = Qt.ItemDataRole.UserRole + 7

    _ROLE_NAMES: ClassVar[dict[int, bytes]] = {
        SYMBOL_ROLE: b"symbol",
        BASE_ROLE: b"base",
        QUOTE_ROLE: b"quote",
        SUBTITLE_ROLE: b"subtitle",
        FAVOURITE_ROLE: b"favourite",
        CURRENT_ROLE: b"current",
        FOCUSED_ROLE: b"focused",
    }

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows: list[dict[str, object]] = []

    def rowCount(self, parent: QModelIndex = _INVALID_INDEX) -> int:
        if parent.isValid():
            return 0
        return len(self._rows)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        row = self._rows[index.row()]
        role_key = self._ROLE_NAMES.get(role)
        if role_key is None:
            return row.get("symbol") if role == Qt.ItemDataRole.DisplayRole else None
        return row[role_key.decode()]

    def roleNames(self) -> dict[int, bytes]:
        return self._ROLE_NAMES.copy()

    def set_rows(self, rows: Sequence[Mapping[str, object]]) -> None:
        """Replace rows and notify views using the simple reset protocol."""
        self.beginResetModel()
        self._rows = [dict(row) for row in rows]
        self.endResetModel()
