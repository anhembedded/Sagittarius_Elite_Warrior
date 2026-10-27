"""Widens a table's columns for rows inserted after the Engine fitted them (`BUG-272`).

The Engine fits a table's columns when its first rows arrive and not again until a reset, and
leaves them `Interactive`. A live table (the Developer mode's event log) is fed by inserts
later, so a row longer than anything in the first batch stayed elided. Re-measuring the whole
column on every insert is what the Engine took out on purpose (its `StretchColumnFiller`
records 21 s for a thousand rows, and a width the person dragged undone on each insert), so
this measures only the inserted rows against the widest content seen so far, and widens a
column only when a row is wider than all of them and than the column is now: a width the person
narrowed stays until a genuinely wider row arrives. The stretch column belongs to the Engine's
`StretchColumnFiller` and is left alone; a long text in it after boot is still the Engine's
(`BUG-272`, Suggested next steps).

Retire when: the Engine's first-rows fitter widens a column for later rows itself.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QAbstractItemModel, QModelIndex
from PySide6.QtWidgets import QTableView
from sagittarius_engine.extensions.pyside_mvc.workbench import ColumnSpec


class InsertedRowsColumnGrowth:
    """Grow-only column widths for a table whose rows arrive by insert."""

    def __init__(
        self,
        view: QTableView,
        proxy: QAbstractItemModel,
        columns: Sequence[ColumnSpec],
    ) -> None:
        self._view = view
        self._proxy = proxy
        self._stretched = frozenset(
            index for index, spec in enumerate(columns) if spec.stretch
        )
        self._widest: dict[int, int] = {}
        proxy.rowsInserted.connect(self._on_rows_inserted)
        proxy.modelReset.connect(self._widest.clear)

    def _on_rows_inserted(self, _parent: QModelIndex, first: int, last: int) -> None:
        header = self._view.horizontalHeader()
        grid_line = (
            1 if self._view.showGrid() else 0
        )  # as `QTableView.sizeHintForColumn`
        # Qt itself looks at no more than this many rows when it measures a column.
        first = max(first, last + 1 - header.resizeContentsPrecision())
        for column in range(header.count()):
            if column in self._stretched or header.isSectionHidden(column):
                continue
            need = grid_line + max(
                self._view.sizeHintForIndex(self._proxy.index(row, column)).width()
                for row in range(first, last + 1)
            )
            if need <= self._widest.get(column, 0):
                continue
            self._widest[column] = need
            if need > header.sectionSize(column):
                header.resizeSection(column, need)
