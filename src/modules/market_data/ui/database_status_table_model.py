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

@par What left this file in PR 4.1b
`rowCount()`, `columnCount()`, `headerData()`, `row_for()` and the first three
branches of `data()` — byte-for-byte identical to the two order-book models PR
1.4b-2 wrote, which neither pair could see because
`presentation/ui/components/` was never in the duplication metric's package set.
They, `SORT_ROLE` and `_as_number()` are `support/ui_kit/table_model.py`'s now.
What stays is what is actually this table's: its columns, the interval sort that
puts `1m` before `15m` before `1h`, the unhealthy-first status sort, the bold
status cell, and the **incremental** row API — `upsert_row()` re-scans one shard
and emits `dataChanged` for that row alone, so the user keeps their selection
and their scroll position, which a `set_rows()` reset would throw away. That is
why the base class holds its rows in a list.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Final

from PySide6.QtCore import (
    QModelIndex,
    QObject,
    QSortFilterProxyModel,
    Qt,
    Signal,
)
from PySide6.QtGui import QFont
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.support.ui_kit.model_indexes import AnyIndex
from Sagittarius_Elite_Warrior.src.support.ui_kit.table_model import (
    SORT_ROLE,
    RowTableModel,
    as_number,
)

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


def _interval_seconds(interval: str) -> int:
    """An interval's length, for sorting. `0` for a code the domain no longer
    recognises — a stale value read back from disk sorts first rather than
    raising in the middle of a `sort()`."""
    try:
        return TimeFrame(interval).to_seconds()
    except ValueError:
        return 0


class DatabaseStatusTableModel(RowTableModel[DatabaseStatusRow]):
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

    HEADERS: ClassVar[tuple[str, ...]] = (
        "Symbol",
        "TF",
        "First record",
        "Last record",
        "Candles",
        "Status",
    )

    #: Right-aligned because the eye compares a column of counts by its last
    #: digit; every other column is text and stays left-aligned.
    RIGHT_ALIGNED: ClassVar[frozenset[int]] = frozenset({TOTAL_CANDLES_COLUMN})

    #: Emitted whenever the row set changes, so a header badge can show a live
    #: count without reaching into this model's internals.
    countsChanged = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._row_index: dict[str, int] = {}

    # -- what this table decides (the rest is `RowTableModel`'s) -----------

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
            return as_number(row.total_candles)
        if column == self.STATUS_COLUMN:
            # Unhealthy first: the point of sorting by status is to bring the
            # shards that need work to the top. Prefixed into one string
            # rather than returned as a `(healthy, text)` tuple, because a
            # tuple reaches `QSortFilterProxyModel.lessThan()` as an opaque
            # `QVariant` it cannot order — the first version of this was a
            # tuple and the sort silently did nothing.
            return f"{1 if row.is_healthy else 0}{row.status_text}"
        return self._display_text(row, column)

    def _role_data(self, row: DatabaseStatusRow, column: int, role: int) -> object:
        """A shard with holes in it gets a bold status cell — the one emphasis
        this table carries, and it replaces a colour: that row is the one the
        user came here to act on (ADR D21 — no palette of our own)."""
        if (
            role == Qt.ItemDataRole.FontRole
            and column == self.STATUS_COLUMN
            and not row.is_healthy
        ):
            font = QFont()
            font.setBold(True)
            return font
        return None

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
