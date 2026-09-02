"""State behind `OpenOrdersTable.qml` — a pure display projection, no
filtering (`EPIC-021I`). Push-based, same shape as `PositionsVM`.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Property, QObject, Signal

from .open_order_row import OpenOrderRow, open_order_rows_to_qml


class OpenOrdersVM(QObject):
    """@brief The full set of currently pending orders, as QML-facing rows."""

    stateChanged = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._rows: list[dict[str, object]] = []

    @Property("QVariantList", notify=stateChanged)
    def rows(self) -> list[dict[str, object]]:
        return self._rows

    def set_rows(self, rows: Sequence[OpenOrderRow]) -> None:
        self._rows = open_order_rows_to_qml(list(rows))
        self.stateChanged.emit()
