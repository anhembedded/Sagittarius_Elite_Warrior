"""One `QAbstractTableModel` shape, for every table in this application.

## Why it exists, and who said so first

`EPIC-025` PR 4.1b. Four models were carrying the same code:
`PositionsTableModel` and `OpenOrdersTableModel` (written by PR 1.4b-2, when the
two live QML tables became `QTableView`s) and `DatabaseStatusTableModel` and
`KLineInspectorTableModel` (written by PR 0.4b, when Data Management was rebuilt
the same way). `rowCount()`, `columnCount()`, `headerData()` and `row_for()` were
**byte-for-byte identical** across all four, `data()` differed only in which
extra roles it served, and `SORT_ROLE` and `_as_number()` were each defined twice
at module level with one of the two copies stripping `"USDT"` and the other not.

Neither pair could see the other. `presentation/ui/components/` was never in
`tools/measure_duplicate_members.py`'s `UI_PACKAGE_GLOBS`, so the metric this
epic is judged on never compared them — the same hole PR 2.1e found for
`common/` and `components/`. It surfaced only when PR 4.1a moved `order_book`
into `modules/trading/ui/`, a package the tool *does* scan, and the ratchet
refused the move.

The duplication was **already written down** before it was measured:
`table_models.py` carried a comment saying `SORT_ROLE` was *"defined per table
family rather than shared with `database_status_table_model.py`'s identical
constant: a component importing a screen is the cross-screen import the guards
refuse, and the shared home for both is `support/ui_kit` in Phase 4."* This is
that home, and this is Phase 4.

## What it does and does not decide

It owns the parts of Qt's contract that have one correct answer:

  · `rowCount()` / `columnCount()` — zero for a valid parent, because a table
    model has no children, and Qt calls both with one.
  · `headerData()` — the horizontal display header, from `HEADERS`.
  · `row_for()` — the row behind an index, `None` when the index is stale. A
    typed accessor rather than a `Qt.UserRole` payload, which is the reasoning
    all four models had already written down separately: a caller that wants the
    row wants the whole row, and `data(index, SomeRole) -> object` makes every
    one of them cast.
  · `data()` as a **template**: display text, the sort value, right-alignment,
    then one hook for everything else.

It decides nothing about a particular table. `HEADERS`, `RIGHT_ALIGNED`,
`_display_text()`, `_sort_value()` and `_role_data()` are each a subclass's, and
the two `@abstractmethod`s are the contract.

@par `@abstractmethod` without `ABC`, the `BaseFeed` pattern
`QAbstractTableModel`'s metaclass is Shiboken's, and mixing `ABCMeta` into it
raises a metaclass conflict. So the decorator documents the contract and the
body raises — `support/ui_kit/base_feed.py` established exactly this, and a
subclass that forgets breaks on its first call with the method's own name in the
message rather than returning `None` and painting an empty table.

@par Generic in the row type, and it was tested rather than assumed
PEP 695 `class RowTableModel[TRow](QAbstractTableModel)` works under PySide6 —
verified by constructing a parametrised subclass before this file was written.
It matters: without it `row_for()` answers `Any`, every panel that reads a row
casts, and `support/ui_kit` is a tree mypy actually checks (`src/presentation/`
is excluded wholesale, which is how four models drifted this far unremarked).
"""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Sequence
from typing import ClassVar, Final

from PySide6.QtCore import QAbstractTableModel, QObject, Qt
from Sagittarius_Elite_Warrior.src.support.ui_kit.model_indexes import AnyIndex

#: The role carrying the comparable value behind a cell's display text, so a
#: numeric column sorts numerically rather than alphabetically. `"-9.00 USDT"`
#: sorts *after* `"+10.00 USDT"` on text, and `"10.00"` before `"9.00"` — which
#: is why every sortable table serves this role and points its
#: `QSortFilterProxyModel` at it.
#:
#: One definition now. It was two, both `UserRole + 1`, in two trees that could
#: not import each other.
SORT_ROLE: Final = Qt.ItemDataRole.UserRole + 1

#: What a right-aligned numeric cell answers for `TextAlignmentRole`. The eye
#: compares a column of numbers by its last digit.
_RIGHT_ALIGN: Final = int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)


def as_number(text: str) -> float:
    """The number a formatted cell means, for sorting.

    Anything unparseable — `"—"` for a value the exchange did not report,
    `"N/A"` for a shard nothing has scanned yet — sorts below every real number
    rather than raising in the middle of a `sort()`.

    The two copies this replaces differed: the order-book one stripped
    `"USDT"`, the Database Status one did not. The union is taken deliberately
    and is safe in both directions, because a count never contains `"USDT"` and
    stripping a substring that is not there is a no-op. Recorded rather than
    silently merged, because a shared helper that quietly changes one caller's
    behaviour is how a de-duplication becomes a defect.
    """
    try:
        return float(text.replace(",", "").replace(" ", "").replace("USDT", ""))
    except ValueError:
        return float("-inf")


class RowTableModel[TRow](QAbstractTableModel):
    """A table of whole rows, where a row is one object rather than N cells."""

    #: The horizontal header, left to right. Its length is `columnCount()`.
    HEADERS: ClassVar[tuple[str, ...]] = ()

    #: Which columns are numeric, and so right-aligned. Empty by default: a
    #: table of text needs no alignment rule.
    RIGHT_ALIGNED: ClassVar[frozenset[int]] = frozenset()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        #: A list rather than a tuple, so a subclass that updates rows in
        #: place can. `DatabaseStatusTableModel` re-scans one `(symbol,
        #: interval)` shard at a time and emits `dataChanged` for that row
        #: alone; forcing it through `set_rows()` would reset the model, drop
        #: the user's selection and their scroll position on every scan.
        #: `rows` hands out a tuple, so no caller can mutate it from outside.
        self._rows: list[TRow] = []

    # -- QAbstractTableModel's contract, which has one right answer --------

    def rowCount(self, parent: AnyIndex | None = None) -> int:
        if parent is not None and parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent: AnyIndex | None = None) -> int:
        if parent is not None and parent.isValid():
            return 0
        return len(self.HEADERS)

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
        if not 0 <= section < len(self.HEADERS):
            return None
        return self.HEADERS[section]

    def data(self, index: AnyIndex, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        """Display text, the sort value, alignment — then `_role_data()`.

        The order matters and is the order all four models already used: a
        stale index answers `None` before any role is considered, so a repaint
        racing a `set_rows()` cannot read past the end of the list.
        """
        row = self.row_for(index)
        if row is None:
            return None
        column = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            return self._display_text(row, column)
        if role == SORT_ROLE:
            return self._sort_value(row, column)
        if role == Qt.ItemDataRole.TextAlignmentRole and column in self.RIGHT_ALIGNED:
            return _RIGHT_ALIGN
        return self._role_data(row, column, role)

    # -- reading and writing whole rows ------------------------------------

    def row_for(self, index: AnyIndex) -> TRow | None:
        """The row behind an index, or `None` when the index is stale."""
        if not index.isValid():
            return None
        if not 0 <= index.row() < len(self._rows):
            return None
        return self._rows[index.row()]

    @property
    def rows(self) -> tuple[TRow, ...]:
        """Every row, as an immutable snapshot."""
        return tuple(self._rows)

    def set_rows(self, rows: Sequence[TRow]) -> None:
        """Replaces every row.

        `beginResetModel()`/`endResetModel()` rather than per-row signals: the
        full set arrives on each update from a feed that does not diff, and a
        reset is the honest description of what happened. Every selection and
        every open persistent index is invalidated, which is why callers that
        care about the selection re-read it afterwards.
        """
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

    def clear(self) -> None:
        self.set_rows(())

    # -- what a particular table decides -----------------------------------

    @abstractmethod
    def _display_text(self, row: TRow, column: int) -> str:
        """The text in this cell. `""` for a column this table does not fill."""
        raise NotImplementedError("_display_text")

    @abstractmethod
    def _sort_value(self, row: TRow, column: int) -> object:
        """The comparable value behind this cell.

        A table whose every column sorts by its display text returns
        `self._display_text(row, column)`; it is still declared here rather
        than defaulted, because a numeric column that forgets to override
        sorts `"10.00"` before `"9.00"` and nothing fails — which is the whole
        defect `SORT_ROLE` exists to prevent.
        """
        raise NotImplementedError("_sort_value")

    def _role_data(self, row: TRow, column: int, role: int) -> object:
        """Any role beyond display, sorting and alignment — a bold cell, a
        monospace font, a foreground colour. `None` means "Qt's default", and
        that is the right answer for most tables, so this is not abstract."""
        return None
