"""The Positions panel — a `QTableView` over every position the account holds.

@details A position is closed by placing an order, not by acting on a row,
so this panel has no action of its own. A host that offers one (the desk's
"Close at market", `EPIC-028J`) adds it with `add_action()`, which shows the
toolbar it otherwise keeps hidden, and reads `selected_row()`. What it gains over the `PositionsTable.qml` it replaces is what the
platform's table brings: column sorting (click "Unrealized PnL" to bring the
worst position to the top), keyboard navigation, native selection and a header
the user can reorder.

**What it keeps**, so neither screen that hosts it had to change:
`set_rows(rows)` with the same `PositionRow` sequence. `root_object` is gone
with the QML it exposed.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QSortFilterProxyModel, Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QStackedWidget,
    QTableView,
    QToolBar,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.position_row import (
    PositionRow,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.table_models import (
    PositionsTableModel,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.table_model import SORT_ROLE

_EMPTY_TEXT = "No open positions."


class PositionsPanel(QWidget):  # base-exempt: a container, not a surface
    """@brief The account's open positions, as the platform's own table."""

    #: The selected row changed, or the rows were replaced.
    selectionChanged = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._model = PositionsTableModel(self)
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)
        self._proxy.setSortRole(SORT_ROLE)

        self._table = QTableView()
        self._table.setObjectName("tblPositions")
        self._table.setModel(self._proxy)
        self._table.setSortingEnabled(True)
        # An explicit initial sort, because `setSortingEnabled(True)` alone
        # leaves Qt to sort by whatever its header's sort indicator happens to
        # default to — which is column 0 in the *opposite* order to what a
        # reader expects, measured. Symbol ascending is the stable order a
        # user can find a position in; every other column is one click away.
        self._table.sortByColumn(
            PositionsTableModel.SYMBOL_COLUMN, Qt.SortOrder.AscendingOrder
        )
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        # One declaration for header and rows both, which is the column-width
        # rule in `ui-presentation-rule.md`: the symbol column takes what it
        # needs, and the numbers share what is left so the table fills its
        # dock at any width.
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(
            PositionsTableModel.SYMBOL_COLUMN, QHeaderView.ResizeMode.ResizeToContents
        )

        self._empty = QLabel(_EMPTY_TEXT)
        self._empty.setObjectName("lblPositionsEmpty")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setWordWrap(True)

        # A stack rather than hiding the table: an empty `QTableView` still
        # draws its header and its grid, which reads as "nothing loaded yet"
        # when the truth is "the account holds nothing".
        self._body = QStackedWidget()
        self._body.setObjectName("stkPositionsBody")
        self._body.addWidget(self._empty)
        self._body.addWidget(self._table)

        self._table.selectionModel().selectionChanged.connect(self.selectionChanged)
        self._toolbar = QToolBar()
        self._toolbar.setObjectName("tbrPositions")
        self._toolbar.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._toolbar)
        layout.addWidget(self._body)
        self._show_body()

    def set_rows(self, rows: Sequence[PositionRow]) -> None:
        """Replaces the table's rows entirely — the feed driving this holds
        the whole set (`EPIC-021H`)."""
        self._model.set_rows(rows)
        self._show_body()
        # A reset clears the selection without a `selectionChanged`.
        self.selectionChanged.emit()

    def add_action(self, action: QAction) -> None:
        """Shows a host's action in the toolbar and the row's context menu."""
        self._toolbar.addAction(action)
        self._toolbar.show()
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)
        self._table.addAction(action)

    def selected_row(self) -> PositionRow | None:
        indexes = self._table.selectionModel().selectedRows()
        if not indexes:
            return None
        return self._model.row_for(self._proxy.mapToSource(indexes[0]))

    @property
    def table(self) -> QTableView:
        """For a host that needs to size or focus the table itself."""
        return self._table

    def _show_body(self) -> None:
        self._body.setCurrentWidget(
            self._table if self._model.rowCount() else self._empty
        )
