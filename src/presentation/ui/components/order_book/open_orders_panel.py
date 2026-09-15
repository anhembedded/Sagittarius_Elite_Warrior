"""The Open Orders panel — a `QTableView` over every pending order, plus the
one action that operates on the selected one.

**What this replaces.** `OpenOrdersTable.qml` + `OpenOrderRow.qml`, whose every
row carried a "Huỷ" button. That shape comes from QML, where a delegate is the
only way to put a control in a row; on the desktop it is what ADR D20 rules
out, and PR 0.4b already answered it for the Database Status table: **the
action moves out of the rows**. One `QAction`, in the toolbar above the table
*and* in the row's context menu, operating on the selected row — `Tab` to the
table, arrow to the order, `Delete` to cancel it.

**A confirmation arrived with it.** The QML button fired the cancel straight at
the Presenter with nothing in between. Cancelling a live order is destructive
and irreversible at the venue, so `Docs/HLD/11_desktop_workbench.md` §11.5 and
the User-Control principle require the dialog: it names the order, its symbol
and its side before anything is sent.

**What it keeps**, so neither screen that hosts it had to change:
`cancelRequested(symbol, client_order_id)` and `set_rows(rows)`.
`root_object` is gone with the QML it exposed.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtCore import QSortFilterProxyModel, Qt, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QMessageBox,
    QStackedWidget,
    QTableView,
    QToolBar,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.order_book.open_order_row import (
    OpenOrderRow,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.order_book.table_models import (
    SORT_ROLE,
    OpenOrdersTableModel,
)

_EMPTY_TEXT = "No pending orders."
_CANCEL_TEXT = "Cancel order"

#: Asked before a cancel is emitted. Returns True to proceed. Injectable so a
#: test drives the panel without a modal dialog waiting for a click that never
#: comes — the default below is the real `QMessageBox`, and this is the shape
#: `database_status_panel.py`'s `ConfirmClear` established.
type ConfirmCancel = Callable[[OpenOrderRow], bool]


def _ask_with_message_box(parent: QWidget, row: OpenOrderRow) -> bool:
    answer = QMessageBox.question(
        parent,
        _CANCEL_TEXT,
        f"Cancel the {row.side.value.upper()} {row.order_type_text} order on "
        f"{row.symbol} ({row.quantity_text} @ {row.price_text})?\n\n"
        "The order is cancelled at the exchange and cannot be restored.",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    return answer == QMessageBox.StandardButton.Yes


class OpenOrdersPanel(QWidget):  # base-exempt: a container, not a surface
    """@brief The account's pending orders, as the platform's own table."""

    #: `EPIC-024B` §0 — the row action a panel forwards to whichever screen
    #: hosts it, identified by the row it was invoked on: `(symbol,
    #: client_order_id)`, not an index into a list the host cannot see.
    cancelRequested = Signal(str, str)

    def __init__(
        self,
        parent: QWidget | None = None,
        confirm_cancel: ConfirmCancel | None = None,
    ) -> None:
        super().__init__(parent)
        self._confirm_cancel: ConfirmCancel = confirm_cancel or (
            lambda row: _ask_with_message_box(self, row)
        )

        self._model = OpenOrdersTableModel(self)
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)
        self._proxy.setSortRole(SORT_ROLE)

        self._cancel_action = QAction(_CANCEL_TEXT, self)
        self._cancel_action.setObjectName("actCancelOrder")
        self._cancel_action.setShortcut(QKeySequence.StandardKey.Delete)
        self._cancel_action.setToolTip(
            "Cancel the selected order at the exchange (Del)"
        )
        self._cancel_action.setEnabled(False)
        self._cancel_action.triggered.connect(self._request_cancel)

        self._toolbar = QToolBar()
        self._toolbar.setObjectName("tbrOpenOrders")
        self._toolbar.addAction(self._cancel_action)

        self._table = QTableView()
        self._table.setObjectName("tblOpenOrders")
        self._table.setModel(self._proxy)
        self._table.setSortingEnabled(True)
        # Symbol ascending, for the reason `positions_panel.py` records: the
        # default sort indicator is not the order anybody asked for.
        self._table.sortByColumn(
            OpenOrdersTableModel.SYMBOL_COLUMN, Qt.SortOrder.AscendingOrder
        )
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        # The same action, reachable the two ways a desktop user expects it.
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)
        self._table.addAction(self._cancel_action)
        self._table.doubleClicked.connect(self._request_cancel)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(
            OpenOrdersTableModel.SYMBOL_COLUMN, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.selectionModel().selectionChanged.connect(self._apply_action_state)

        self._empty = QLabel(_EMPTY_TEXT)
        self._empty.setObjectName("lblOpenOrdersEmpty")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setWordWrap(True)

        self._body = QStackedWidget()
        self._body.setObjectName("stkOpenOrdersBody")
        self._body.addWidget(self._empty)
        self._body.addWidget(self._table)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._toolbar)
        layout.addWidget(self._body)
        self._show_body()

    def set_rows(self, rows: Sequence[OpenOrderRow]) -> None:
        """Replaces the table's rows entirely — the feed driving this holds
        the whole set (`EPIC-021H`)."""
        self._model.set_rows(rows)
        self._show_body()
        # A reset clears the selection, and an action enabled with nothing
        # selected is an action that does nothing when pressed.
        self._apply_action_state()

    @property
    def table(self) -> QTableView:
        """For a host that needs to size or focus the table itself."""
        return self._table

    @property
    def cancel_action(self) -> QAction:
        """So a surface can put the same action in its own header or menu —
        one `QAction` per user action, wherever it is shown."""
        return self._cancel_action

    def selected_row(self) -> OpenOrderRow | None:
        indexes = self._table.selectionModel().selectedRows()
        if not indexes:
            return None
        return self._model.row_for(self._proxy.mapToSource(indexes[0]))

    def _apply_action_state(self) -> None:
        self._cancel_action.setEnabled(self.selected_row() is not None)

    def _request_cancel(self) -> None:
        row = self.selected_row()
        if row is None:
            return
        if not self._confirm_cancel(row):
            return
        self.cancelRequested.emit(row.symbol, row.client_order_id)

    def _show_body(self) -> None:
        self._body.setCurrentWidget(
            self._table if self._model.rowCount() else self._empty
        )
