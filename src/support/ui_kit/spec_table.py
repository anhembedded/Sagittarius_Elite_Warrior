"""`SpecTable` — a `RowTableModel` shown the one way every table of this
application is shown (`EPIC-033N`).

A panel hands over its model and says what an empty table should tell the
user; `configure_spec_view` does everything a column's kind decides
(header, alignment, sorting on the raw value, whole-row selection, no
editing, values written by `APP_VALUE_FORMATTER`, a stretch column that
never squeezes below its content), and the Engine's
`EmptyStateStack` shows the instruction while there are no rows.

Every panel used to do this by hand: a `QSortFilterProxyModel` pointed at a
`SORT_ROLE`, five view setters, a header resize mode per column, a `QLabel`
and a `QStackedWidget` for the empty case — the same thirty lines in each of
the order book's three panels, and slightly different in each.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.model_indexes import AnyIndex
from Sagittarius_Elite_Warrior.src.support.ui_kit.spec_view import configure_spec_view
from Sagittarius_Elite_Warrior.src.support.ui_kit.table_model import RowTableModel
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import (
    APP_VALUE_FORMATTER,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    EmptyStateStack,
    IValueFormatter,
    Selection,
    SpecProxyModel,
)


def displayed_text(view: QAbstractItemView, row: int, column: int) -> str:
    """The text the view paints in a cell — asked of its own delegate, so it
    is what the user reads, formatter and all."""
    model = view.model()
    delegate = view.itemDelegate()
    if model is None or not isinstance(delegate, QStyledItemDelegate):
        raise TypeError("the view has no model or no styled delegate")
    option = QStyleOptionViewItem()
    delegate.initStyleOption(option, model.index(row, column))
    return str(option.text)  # type: ignore[attr-defined]


class SpecTable[TRow]:
    """A table view over `model`, inside the stack that shows `empty_text`
    while it has no rows."""

    def __init__(
        self,
        model: RowTableModel[TRow],
        *,
        object_name: str,
        empty_text: str,
        selection: Selection = Selection.SINGLE,
        formatter: IValueFormatter = APP_VALUE_FORMATTER,
    ) -> None:
        self.model = model
        self.view = QTableView()
        self.view.setObjectName(object_name)
        self.proxy: SpecProxyModel = configure_spec_view(
            self.view,
            model,
            model.COLUMNS,
            formatter=formatter,
            selection=selection,
        )
        self.body: QWidget = EmptyStateStack(self.view, empty_text)
        self.body.setObjectName(f"{object_name}Body")

    def row_at(self, proxy_index: AnyIndex) -> TRow | None:
        """The row behind an index of the view, which is the proxy's."""
        return self.model.row_for(self.proxy.mapToSource(proxy_index))

    def selected_rows(self) -> list[TRow]:
        """The selected rows, top to bottom as the view shows them."""
        indexes = sorted(
            self.view.selectionModel().selectedRows(), key=lambda index: index.row()
        )
        return [row for index in indexes if (row := self.row_at(index)) is not None]

    def selected_row(self) -> TRow | None:
        rows = self.selected_rows()
        return rows[0] if rows else None

    def select_first(self, matches: Callable[[TRow], bool]) -> bool:
        """Selects the first row, as the view orders them, that `matches`;
        `False` when none does. A model reset clears the selection; a panel
        whose rows are replaced on every query calls this to keep the row
        the person had selected, by its identity rather than its position."""
        for proxy_row in range(self.proxy.rowCount()):
            row = self.row_at(self.proxy.index(proxy_row, 0))
            if row is not None and matches(row):
                self.view.selectRow(proxy_row)
                return True
        return False

    def text(self, row: int, column: int) -> str:
        """What the view shows at `row` (as sorted) and `column`."""
        return displayed_text(self.view, row, column)

    def sort_by(self, column: int) -> None:
        """Sorts ascending by `column`, as a first click on its header does."""
        self.view.sortByColumn(column, Qt.SortOrder.AscendingOrder)
