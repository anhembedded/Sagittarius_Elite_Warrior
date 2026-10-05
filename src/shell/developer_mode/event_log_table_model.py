"""The Developer mode's event log: one row per emit or failed handler,
oldest at the top, the newest `limit` kept (`EPIC-033P`)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import ClassVar

from PySide6.QtCore import QModelIndex, QObject
from Sagittarius_Elite_Warrior.src.support.ui_kit.table_model import RowTableModel
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ColumnKind,
    ColumnSpec,
    DisplayValue,
)

from .bus_event_recorder import BusEventRecord

#: How many rows the log keeps; older ones scroll off the top.
DEFAULT_LIMIT = 5000


class EventLogTableModel(RowTableModel[BusEventRecord]):
    """@brief What the bus did, newest last."""

    COLUMNS: ClassVar[tuple[ColumnSpec, ...]] = (
        ColumnSpec("at", "Time", ColumnKind.TIMESTAMP),
        ColumnSpec("event", "Event", ColumnKind.TEXT),
        ColumnSpec("handlers", "Handlers", ColumnKind.QUANTITY),
        ColumnSpec("outcome", "Outcome", ColumnKind.TEXT, stretch=True),
    )

    def __init__(
        self, limit: int = DEFAULT_LIMIT, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._limit = limit

    def append(self, records: Sequence[BusEventRecord]) -> None:
        """Adds a drained batch at the bottom and drops what exceeds the
        limit from the top: row signals, not a reset, so the person's
        selection and scroll position survive."""
        if not records:
            return
        incoming = list(records)
        first = len(self._rows)
        self.beginInsertRows(QModelIndex(), first, first + len(incoming) - 1)
        self._rows.extend(incoming)
        self.endInsertRows()
        excess = len(self._rows) - self._limit
        if excess > 0:
            self.beginRemoveRows(QModelIndex(), 0, excess - 1)
            del self._rows[:excess]
            self.endRemoveRows()

    def _value(self, row: BusEventRecord, column: int) -> DisplayValue:
        values: tuple[DisplayValue, ...] = (
            row.at,
            row.event,
            row.handlers,
            row.outcome,
        )
        return values[column]
