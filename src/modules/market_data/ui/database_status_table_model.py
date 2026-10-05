"""The Database Status table — one row per `(symbol, interval)` shard on disk.

**What changed in `EPIC-025` PR 0.4b.** This model already was a
`QAbstractTableModel`, but only in name: it declared `columnCount() == 1` and
served seven custom roles, because its one consumer was a QML `ListView` whose
delegate drew the six columns itself (`DatabaseStatusRow.qml`). A `QTableView`
asks for `DisplayRole` per `(row, column)` and for `headerData()` — neither of
which existed. So the six columns move out of the deleted delegate and into
this model, where the platform's own table can render them (ADR D20).

**Sorting sorts the facts.** Since `EPIC-033N` the columns are specs and the
cells raw values — a candle count is an `int`, a first record a `datetime`,
an interval its length in seconds (written back as its code through
`TIMEFRAME_KEY`) — so `"1,234"` sorts after `"9"` and `1m` before `15m` before
`1h` because the values compare that way. Until then the cells were text and a
`SORT_ROLE` stood beside them with the facts.

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
What stays is what is actually this table's: its columns, the bold status
cell, and the **incremental** row API — `upsert_row()` re-scans one shard
and emits `dataChanged` for that row alone, so the user keeps their selection
and their scroll position, which a `set_rows()` reset would throw away. That is
why the base class holds its rows in a list.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar, Final

from PySide6.QtCore import (
    QModelIndex,
    QObject,
    QSortFilterProxyModel,
    Qt,
    Signal,
)
from PySide6.QtGui import QFont
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.support.ui_kit.model_indexes import AnyIndex
from Sagittarius_Elite_Warrior.src.support.ui_kit.table_model import RowTableModel
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import (
    TIMEFRAME_KEY,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ColumnKind,
    ColumnSpec,
    DisplayValue,
)

#: Statuses that mean "no gaps" — everything else is rendered as a problem.
#: Mirrors the strings the Presenter forwards from DatabaseStatusDTO.
HEALTHY_STATUSES = frozenset({"OK", "0 gaps found!"})

#: `EPIC-027A` — every shard this screen can show is Spot today (Phase 1 has
#: no second market with real data), so `DatabaseStatusRow.market` defaults
#: here rather than widening `upsert_row()`/`StatusRowUpdate` across the
#: cross-thread signal boundary those two guard against changing lightly
#: (see this module's own docstring §"What left this file"). A real market
#: filter/column value arrives with `EPIC-027D`'s selector, once a second
#: market has data to distinguish.
_MARKET_LABEL_SPOT = MarketType.SPOT.value.capitalize()


@dataclass
class DatabaseStatusRow:
    """One symbol/interval line in the DB status table."""

    symbol: str
    first_record: datetime | None
    last_record: datetime | None
    total_candles: int
    status_text: str
    interval: str = TimeFrame.ONE_MINUTE.value
    market: str = _MARKET_LABEL_SPOT

    @property
    def key(self) -> str:
        return f"{self.symbol}:{self.interval}" if self.interval else self.symbol

    @property
    def is_healthy(self) -> bool:
        return self.status_text in HEALTHY_STATUSES


def _interval_seconds(interval: str) -> int | None:
    """An interval's length, the value its cell holds. `None` — an empty cell
    — for a code the domain no longer recognises, a stale value read back
    from disk."""
    try:
        return TimeFrame(interval).to_seconds()
    except ValueError:
        return None


class DatabaseStatusTableModel(RowTableModel[DatabaseStatusRow]):
    """
    @brief Table model backing the Database screen's per-symbol/interval
    status table.

    @details Rows are keyed by `(symbol, interval)` and updated in place, so
    re-scanning a shard refreshes its line instead of stacking a second one.
    """

    SYMBOL_COLUMN: Final = 0
    INTERVAL_COLUMN: Final = 1
    STATUS_COLUMN: Final = 5

    COLUMNS: ClassVar[tuple[ColumnSpec, ...]] = (
        ColumnSpec("symbol", "Symbol", ColumnKind.TEXT),
        ColumnSpec(TIMEFRAME_KEY, "TF", ColumnKind.DURATION),
        ColumnSpec("first_record", "First record", ColumnKind.TIMESTAMP),
        ColumnSpec("last_record", "Last record", ColumnKind.TIMESTAMP),
        ColumnSpec("candles", "Candles", ColumnKind.QUANTITY),
        ColumnSpec("status", "Status", ColumnKind.STATUS, stretch=True),
        ColumnSpec("market", "Market", ColumnKind.TEXT),
    )

    #: Emitted whenever the row set changes, so a header badge can show a live
    #: count without reaching into this model's internals.
    countsChanged = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._row_index: dict[str, int] = {}

    # -- what this table decides (the rest is `RowTableModel`'s) -----------

    def _value(self, row: DatabaseStatusRow, column: int) -> DisplayValue:
        # The status sorts unhealthy first on its own: "3 gaps found!" is
        # before "OK" because a digit is before a letter.
        values: tuple[DisplayValue, ...] = (
            row.symbol,
            _interval_seconds(row.interval),
            row.first_record,
            row.last_record,
            row.total_candles,
            row.status_text,
            row.market,
        )
        return values[column]

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
        first_record: datetime | None,
        last_record: datetime | None,
        total_candles: int,
        status_text: str,
        interval: str = TimeFrame.ONE_MINUTE.value,
    ) -> None:
        """
        @brief Updates the row for this symbol/interval, appending it if it
        isn't present yet.
        """
        row = DatabaseStatusRow(
            symbol=symbol,
            first_record=first_record,
            last_record=last_record,
            total_candles=total_candles,
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

    @details Filters only. The panel shows it through `configure_item_view`,
    whose own proxy above this one sorts and aligns (`EPIC-033N`).
    """

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._needle = ""

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
        # The row, not the cells: the interval's cell holds seconds.
        if not isinstance(model, DatabaseStatusTableModel):
            return True
        row = model.row_for(model.index(source_row, 0, source_parent))
        if row is None:
            return False
        return (
            self._needle in row.symbol.lower() or self._needle in row.interval.lower()
        )
