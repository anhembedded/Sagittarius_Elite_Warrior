"""The Database Status table — one row per `(symbol, interval)` shard on disk.

**What changed in `EPIC-025` PR 0.4b.** This model already was a
`QAbstractTableModel`, but only in name: it declared `columnCount() == 1` and
served seven custom roles, because its one consumer was a QML `ListView` whose
delegate drew the six columns itself (`DatabaseStatusRow.qml`). A `QTableView`
asks for `DisplayRole` per `(row, column)` and for `headerData()` — neither of
which existed. So the six columns move out of the deleted delegate and into
this model, where the platform's own table can render them (ADR D20).

**Sorting comes for free, and had to be made correct.** `QSortFilterProxyModel`
sorts on the role it is given, and `DisplayRole` here is display *text*:
`"1,234"` sorts before `"9"`, and `"15m"` before `"1h"` before `"1m"`. So the
model also serves `SortRole`, whose values are the comparable facts behind the
text — an `int` candle count, an interval's length in seconds — and the panel
points the proxy at it. This is the first column sorting this table has ever
had; the QML `ListView` had none.

**No colour.** The old delegate painted the status cell green or red from
`Theme.success`/`Theme.danger`. ADR D21 leaves colour only where it carries
meaning and only through a `QPalette` role or a per-widget property, and Qt
has no palette role meaning "this shard has holes in it" — so health is
carried by the text itself (`"OK"` against `"3 gaps found!"`), by a bold
status cell, and by the `Sync gaps` action being enabled on exactly the rows
that have gaps.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Final

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    QSortFilterProxyModel,
    Qt,
    Signal,
)
from PySide6.QtGui import QFont
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame

#: Statuses that mean "no gaps" — everything else is rendered as a problem.
#: Mirrors the strings the Presenter forwards from DatabaseStatusDTO.
HEALTHY_STATUSES = frozenset({"OK", "0 gaps found!"})

#: The role carrying the comparable value behind a cell's display text, so a
#: numeric column sorts numerically. `UserRole` itself is left free: Qt's own
#: item views use it for application data and a future delegate may want it.
SORT_ROLE: Final = Qt.ItemDataRole.UserRole + 1

#: Any Qt index type a model method may be handed. PySide6 passes
#: `QPersistentModelIndex` to `data()` in some call paths, so an annotation of
#: `QModelIndex` alone is a lie mypy cannot catch but Qt can produce.
type AnyIndex = QModelIndex | QPersistentModelIndex


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


def _interval_seconds(interval: str) -> int:
    """An interval's length, for sorting. `0` for a code the domain no longer
    recognises — a stale value read back from disk sorts first rather than
    raising in the middle of a `sort()`."""
    try:
        return TimeFrame(interval).to_seconds()
    except ValueError:
        return 0


def _as_number(text: str) -> float:
    """The number a formatted count means, for sorting. Display text arrives
    from the Presenter already grouped (`"1,234"`), and `-` or `N/A` stands in
    for "nothing scanned yet" — which sorts as less than any real count."""
    try:
        return float(text.replace(",", "").replace(" ", ""))
    except ValueError:
        return float("-inf")


class DatabaseStatusTableModel(QAbstractTableModel):
    """
    @brief Table model backing the Database screen's per-symbol/interval
    status table.

    @details Rows are keyed by `(symbol, interval)` and updated in place, so
    re-scanning a shard refreshes its line instead of stacking a second one.
    """

    SYMBOL_COLUMN: Final = 0
    INTERVAL_COLUMN: Final = 1
    FIRST_RECORD_COLUMN: Final = 2
    LAST_RECORD_COLUMN: Final = 3
    TOTAL_CANDLES_COLUMN: Final = 4
    STATUS_COLUMN: Final = 5

    _HEADERS: ClassVar[tuple[str, ...]] = (
        "Symbol",
        "TF",
        "First record",
        "Last record",
        "Candles",
        "Status",
    )

    #: Right-aligned because the eye compares a column of counts by its last
    #: digit; every other column is text and stays left-aligned.
    _RIGHT_ALIGNED: ClassVar[frozenset[int]] = frozenset({TOTAL_CANDLES_COLUMN})

    #: Emitted whenever the row set changes, so a header badge can show a live
    #: count without reaching into this model's internals.
    countsChanged = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._rows: list[DatabaseStatusRow] = []
        self._row_index: dict[str, int] = {}

    # ------------------------------------------------------------------ #
    # QAbstractTableModel contract
    # ------------------------------------------------------------------ #

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
            and column == self.STATUS_COLUMN
            and not row.is_healthy
        ):
            # The one emphasis this table carries, and it replaces a colour:
            # a shard with holes in it is the row the user came here to act
            # on (ADR D21 — no palette of our own).
            font = QFont()
            font.setBold(True)
            return font
        return None

    def _display_text(self, row: DatabaseStatusRow, column: int) -> str:
        return {
            self.SYMBOL_COLUMN: row.symbol,
            self.INTERVAL_COLUMN: row.interval,
            self.FIRST_RECORD_COLUMN: row.first_record,
            self.LAST_RECORD_COLUMN: row.last_record,
            self.TOTAL_CANDLES_COLUMN: row.total_candles,
            self.STATUS_COLUMN: row.status_text,
        }.get(column, "")

    def _sort_value(self, row: DatabaseStatusRow, column: int) -> object:
        if column == self.INTERVAL_COLUMN:
            return _interval_seconds(row.interval)
        if column == self.TOTAL_CANDLES_COLUMN:
            return _as_number(row.total_candles)
        if column == self.STATUS_COLUMN:
            # Unhealthy first: the point of sorting by status is to bring the
            # shards that need work to the top. Prefixed into one string
            # rather than returned as a `(healthy, text)` tuple, because a
            # tuple reaches `QSortFilterProxyModel.lessThan()` as an opaque
            # `QVariant` it cannot order — the first version of this was a
            # tuple and the sort silently did nothing.
            return f"{1 if row.is_healthy else 0}{row.status_text}"
        return self._display_text(row, column)

    # ------------------------------------------------------------------ #
    # Reading one row as a row, not as six cells
    # ------------------------------------------------------------------ #

    def row_for(self, index: AnyIndex) -> DatabaseStatusRow | None:
        """The row behind an index, or `None` when the index is stale.

        A typed accessor rather than a `Qt.UserRole` payload: the panel needs
        the whole row (its symbol, its interval and whether it has gaps) to
        decide which actions apply, and `data(index, SomeRole)` returning an
        `object` would make every caller cast.
        """
        if not index.isValid():
            return None
        if not 0 <= index.row() < len(self._rows):
            return None
        return self._rows[index.row()]

    @property
    def rows(self) -> list[DatabaseStatusRow]:
        return list(self._rows)

    def gap_targets(self) -> list[tuple[str, str]]:
        """`(symbol, interval)` of every shard whose status reports gaps."""
        return [(row.symbol, row.interval) for row in self._rows if not row.is_healthy]

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
            self.dataChanged.emit(
                self.index(existing, 0),
                self.index(existing, self.columnCount() - 1),
            )

        self.countsChanged.emit()

    def remove_symbol(self, symbol: str, interval: str | None = None) -> None:
        """
        @brief Removes rows matching symbol (and optionally interval).
        """
        keys_to_remove = {
            row.key
            for row in self._rows
            if row.symbol == symbol and (interval is None or row.interval == interval)
        }
        if not keys_to_remove:
            return

        self.beginResetModel()
        self._rows = [row for row in self._rows if row.key not in keys_to_remove]
        self._row_index = {row.key: i for i, row in enumerate(self._rows)}
        self.endResetModel()
        self.countsChanged.emit()

    def clear(self) -> None:
        self.beginResetModel()
        self._rows.clear()
        self._row_index.clear()
        self.endResetModel()
        self.countsChanged.emit()


class DatabaseStatusFilterProxy(QSortFilterProxyModel):
    """
    @brief Client-side search over an already-loaded `DatabaseStatusTableModel`.
    Matches search text against symbol or interval, case-insensitively.
    """

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._needle = ""
        self.setSortRole(SORT_ROLE)

    def set_search_text(self, text: str) -> None:
        needle = (text or "").strip().lower()
        if needle == self._needle:
            return
        self._needle = needle
        # `invalidate()`, not `invalidateFilter()`: PySide6 6.11 marks all
        # three `invalidate*Filter()` overloads deprecated and warns on every
        # keystroke in the search box. `invalidate()` re-runs the sort as well
        # as the filter, which is free here — the table holds tens of rows.
        self.invalidate()

    def filterAcceptsRow(self, source_row: int, source_parent: AnyIndex) -> bool:
        if not self._needle:
            return True

        model = self.sourceModel()
        if model is None:
            return True

        # Symbol and interval only, not every column: a search for "1m" must
        # not match a row because its *status text* happens to contain it.
        for column in (
            DatabaseStatusTableModel.SYMBOL_COLUMN,
            DatabaseStatusTableModel.INTERVAL_COLUMN,
        ):
            index = model.index(source_row, column, source_parent)
            text = str(model.data(index, Qt.ItemDataRole.DisplayRole) or "")
            if self._needle in text.lower():
                return True
        return False
