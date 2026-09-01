from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QSortFilterProxyModel,
    Qt,
    Signal,
    Slot,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame

#: Statuses that mean "no gaps" — everything else is rendered as a problem.
#: Mirrors the strings the Presenter forwards from DatabaseStatusDTO.
HEALTHY_STATUSES = frozenset({"OK", "0 gaps found!"})


@dataclass
class DatabaseStatusRow:
    """One symbol/interval line in the DB status table."""

    symbol: str
    first_record: str
    last_record: str
    total_candles: str
    status_text: str
    interval: str = TimeFrame.ONE_MINUTE.value

    @property
    def key(self) -> str:
        return f"{self.symbol}:{self.interval}" if self.interval else self.symbol

    @property
    def is_healthy(self) -> bool:
        return self.status_text in HEALTHY_STATUSES


class DatabaseStatusTableModel(QAbstractTableModel):
    """
    @brief Table model backing the Database screen's per-symbol/interval
    status table in QML.

    @details
    Rows are keyed by (symbol, interval) and updated in place.
    Exposes named roles so QML delegates address fields by role name (`model.symbol`, `model.interval`).
    """

    SymbolRole = Qt.ItemDataRole.UserRole + 1
    FirstRecordRole = Qt.ItemDataRole.UserRole + 2
    LastRecordRole = Qt.ItemDataRole.UserRole + 3
    TotalCandlesRole = Qt.ItemDataRole.UserRole + 4
    StatusTextRole = Qt.ItemDataRole.UserRole + 5
    IsHealthyRole = Qt.ItemDataRole.UserRole + 6
    IntervalRole = Qt.ItemDataRole.UserRole + 7

    _ROLE_NAMES: ClassVar[dict[int, bytes]] = {
        SymbolRole: b"symbol",
        FirstRecordRole: b"firstRecord",
        LastRecordRole: b"lastRecord",
        TotalCandlesRole: b"totalCandles",
        StatusTextRole: b"statusText",
        IsHealthyRole: b"isHealthy",
        IntervalRole: b"interval",
    }

    #: Emitted whenever the row set changes, so QML can show live counts
    #: without reaching into the model's internals.
    countsChanged = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows: list[DatabaseStatusRow] = []
        self._row_index: dict[str, int] = {}

    # ------------------------------------------------------------------ #
    # QAbstractTableModel contract
    # ------------------------------------------------------------------ #

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: B008 - Qt override signature requires this default
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()) -> int:  # noqa: B008 - Qt override signature requires this default
        return 0 if parent.isValid() else 1

    def roleNames(self) -> dict:
        return dict(self._ROLE_NAMES)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None

        row = self._rows[index.row()]
        if role == self.SymbolRole:
            return row.symbol
        if role == self.FirstRecordRole:
            return row.first_record
        if role == self.LastRecordRole:
            return row.last_record
        if role == self.TotalCandlesRole:
            return row.total_candles
        if role == self.StatusTextRole:
            return row.status_text
        if role == self.IsHealthyRole:
            return row.is_healthy
        if role == self.IntervalRole:
            return row.interval
        return None

    # ------------------------------------------------------------------ #
    # Mutation API (driven by the Presenter)
    # ------------------------------------------------------------------ #

    def upsert_row(
        self,
        symbol: str,
        first_record: str,
        last_record: str,
        total_candles: str,
        status_text: str,
        interval: str = TimeFrame.ONE_MINUTE.value,
    ) -> None:
        """
        @brief Updates the row for this symbol/interval, appending it if it
        isn't present yet.
        """
        row = DatabaseStatusRow(
            symbol=symbol,
            first_record=str(first_record),
            last_record=str(last_record),
            total_candles=str(total_candles),
            status_text=status_text,
            interval=interval,
        )

        existing = self._row_index.get(row.key)
        if existing is None:
            position = len(self._rows)
            self.beginInsertRows(QModelIndex(), position, position)
            self._rows.append(row)
            self._row_index[row.key] = position
            self.endInsertRows()
        else:
            self._rows[existing] = row
            index = self.index(existing, 0)
            self.dataChanged.emit(index, index, list(self._ROLE_NAMES.keys()))

        self.countsChanged.emit()

    def remove_symbol(self, symbol: str, interval: str | None = None) -> None:
        """
        @brief Removes rows matching symbol (and optionally interval).
        """
        keys_to_remove = [
            r.key
            for r in self._rows
            if r.symbol == symbol and (interval is None or r.interval == interval)
        ]
        if not keys_to_remove:
            return

        self.beginResetModel()
        self._rows = [r for r in self._rows if r.key not in keys_to_remove]
        self._row_index = {r.key: i for i, r in enumerate(self._rows)}
        self.endResetModel()
        self.countsChanged.emit()

    def clear(self) -> None:
        self.beginResetModel()
        self._rows.clear()
        self._row_index.clear()
        self.endResetModel()
        self.countsChanged.emit()

    # ------------------------------------------------------------------ #
    # Read helpers (QML-callable)
    # ------------------------------------------------------------------ #

    @Slot(int, result=str)
    def symbolAt(self, row: int) -> str:
        return self._rows[row].symbol if 0 <= row < len(self._rows) else ""

    @Slot(int, result=str)
    def intervalAt(self, row: int) -> str:
        return (
            self._rows[row].interval
            if 0 <= row < len(self._rows)
            else TimeFrame.ONE_MINUTE.value
        )

    def gap_targets(self) -> list[tuple[str, str]]:
        """List of (symbol, interval) tuples whose status indicates missing data."""
        return [(row.symbol, row.interval) for row in self._rows if not row.is_healthy]

    @property
    def rows(self) -> list[DatabaseStatusRow]:
        return list(self._rows)


class DatabaseStatusFilterProxy(QSortFilterProxyModel):
    """
    @brief Client-side search over an already-loaded DatabaseStatusTableModel.
    Matches search text against symbol or interval, case-insensitively.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._needle = ""

    def set_search_text(self, text: str) -> None:
        needle = (text or "").strip().lower()
        if needle == self._needle:
            return
        self._needle = needle
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        if not self._needle:
            return True

        model = self.sourceModel()
        if model is None:
            return True

        index = model.index(source_row, 0, source_parent)
        symbol = model.data(index, DatabaseStatusTableModel.SymbolRole) or ""
        interval = model.data(index, DatabaseStatusTableModel.IntervalRole) or ""
        return (self._needle in symbol.lower()) or (self._needle in interval.lower())
