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
  · `headerData()` — the horizontal header, from `COLUMNS`' titles.
  · `row_for()` — the row behind an index, `None` when the index is stale. A
    typed accessor rather than a `Qt.UserRole` payload, which is the reasoning
    all four models had already written down separately: a caller that wants the
    row wants the whole row, and `data(index, SomeRole) -> object` makes every
    one of them cast.
  · `data()` as a **template**: the raw value, then one hook for everything
    else.

It decides nothing about a particular table. `COLUMNS`, `_value()` and
`_role_data()` are each a subclass's, and the `@abstractmethod` is the
contract.

@par Raw values since `EPIC-033N`
A cell's `DisplayRole` is the raw value — a float, a `datetime`, a word — and
`COLUMNS` says what kind each column holds. A panel shows the model through
the Engine's `configure_item_view(view, model, model.COLUMNS,
formatter=APP_VALUE_FORMATTER)`, whose delegate writes every cell through the
application's one `AppValueFormatter` and whose proxy sorts on the raw value
and aligns by kind. Until then a model returned display *text*, so it also
had to serve a `SORT_ROLE` with the number behind it (`"-9.00 USDT"` sorted
after `"+10.00 USDT"` on text), declare which columns were numeric, and format
every value itself — which is how one price came to print two ways on two
screens. `SORT_ROLE`, `as_number()`, `HEADERS`, `RIGHT_ALIGNED`,
`_display_text()` and `_sort_value()` are gone with that.

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
from typing import ClassVar

from PySide6.QtCore import QAbstractTableModel, QObject, Qt
from Sagittarius_Elite_Warrior.src.support.ui_kit.model_indexes import AnyIndex
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ColumnSpec,
    DisplayValue,
)


class RowTableModel[TRow](QAbstractTableModel):
    """A table of whole rows, where a row is one object rather than N cells."""

    #: The columns, left to right: key, header title and kind. Its length is
    #: `columnCount()`; `configure_item_view` takes it as the view's specs.
    COLUMNS: ClassVar[tuple[ColumnSpec, ...]] = ()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        #: A list rather than a tuple, so a subclass that updates rows in
        #: place can. `DatabaseStatusTableModel` re-scans one `(symbol,
        #: interval)` shard at a time and emits `dataChanged` for that row
        #: alone; forcing it through `set_rows()` would reset the model, drop
        #: the user's selection and their scroll position on every scan.
        #: `rows` hands out a tuple, so no caller can mutate it from outside.
        self._rows: list[TRow] = []

    @classmethod
    def column(cls, key: str) -> int:
        """The index of the column whose spec has `key`."""
        for index, spec in enumerate(cls.COLUMNS):
            if spec.key == key:
                return index
        raise KeyError(f"{cls.__name__} has no column {key!r}")

    # -- QAbstractTableModel's contract, which has one right answer --------

    def rowCount(self, parent: AnyIndex | None = None) -> int:
        if parent is not None and parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent: AnyIndex | None = None) -> int:
        if parent is not None and parent.isValid():
            return 0
        return len(self.COLUMNS)

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
        if not 0 <= section < len(self.COLUMNS):
            return None
        return self.COLUMNS[section].title

    def data(self, index: AnyIndex, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        """The raw value, then `_role_data()`.

        A stale index answers `None` before any role is considered, so a
        repaint racing a `set_rows()` cannot read past the end of the list.
        """
        row = self.row_for(index)
        if row is None:
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            return self._value(row, index.column())
        return self._role_data(row, index.column(), role)

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
    def _value(self, row: TRow, column: int) -> DisplayValue:
        """The raw value in this cell, of its column's kind; `None` when the
        value is unknown. The formatter writes it, the proxy sorts on it."""
        raise NotImplementedError("_value")

    def _role_data(self, row: TRow, column: int, role: int) -> object:
        """Any role beyond the value — a bold cell, a tooltip. `None` means
        "Qt's default", and that is the right answer for most tables, so this
        is not abstract."""
        return None
