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

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QMessageBox,
    QTableView,
    QToolBar,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.open_order_row import (
    OpenOrderRow,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.table_models import (
    OpenOrdersTableModel,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.spec_table import SpecTable
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import (
    display_number,
    write_value,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import ColumnKind

_EMPTY_TEXT = "No pending orders."
_CANCEL_TEXT = "Cancel order"

#: Asked before a cancel is emitted. Returns True to proceed. Injectable so a
#: test drives the panel without a modal dialog waiting for a click that never
#: comes — the default below is the real `QMessageBox`, and this is the shape
#: `database_status_panel.py`'s `ConfirmClear` established.
type ConfirmCancel = Callable[[OpenOrderRow], bool]


def cancel_question(row: OpenOrderRow) -> str:
    """What the confirmation asks, with the order's values written as the
    table writes them; a market order has no price to name."""
    quantity = write_value(ColumnKind.QUANTITY, display_number(row.quantity))
    at_price = (
        f" @ {write_value(ColumnKind.PRICE, display_number(row.price))}"
        if row.price is not None
        else ""
    )
    return (
        f"Cancel the {row.side.value.upper()} {row.order_type} order on "
        f"{row.symbol} ({quantity}{at_price})?"
    )


def _ask_with_message_box(parent: QWidget, row: OpenOrderRow) -> bool:
    answer = QMessageBox.question(
        parent,
        _CANCEL_TEXT,
        f"{cancel_question(row)}\n\n"
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

        # Symbol ascending, for the reason `positions_panel.py` records.
        self._table = SpecTable(
            self._model, object_name="tblOpenOrders", empty_text=_EMPTY_TEXT
        )
        self._table.sort_by(OpenOrdersTableModel.column("symbol"))
        view = self._table.view
        # The same action, reachable the two ways a desktop user expects it.
        view.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)
        view.addAction(self._cancel_action)
        view.doubleClicked.connect(self._request_cancel)
        view.selectionModel().selectionChanged.connect(self._apply_action_state)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._toolbar)
        layout.addWidget(self._table.body)

    def set_rows(self, rows: Sequence[OpenOrderRow]) -> None:
        """Replaces the table's rows entirely — the feed driving this holds
        the whole set (`EPIC-021H`)."""
        self._model.set_rows(rows)
        # A reset clears the selection, and an action enabled with nothing
        # selected is an action that does nothing when pressed.
        self._apply_action_state()

    @property
    def table(self) -> QTableView:
        """For a host that needs to size or focus the table itself."""
        return self._table.view

    @property
    def cancel_action(self) -> QAction:
        """So a surface can put the same action in its own header or menu —
        one `QAction` per user action, wherever it is shown."""
        return self._cancel_action

    def add_action(self, action: QAction) -> None:
        """Puts a host's own action beside "Cancel order", in the toolbar
        and the row's context menu (`EPIC-028J`'s "Cancel all")."""
        self._toolbar.addAction(action)
        self._table.view.addAction(action)

    def selected_row(self) -> OpenOrderRow | None:
        return self._table.selected_row()

    def _apply_action_state(self) -> None:
        self._cancel_action.setEnabled(self.selected_row() is not None)

    def _request_cancel(self) -> None:
        row = self.selected_row()
        if row is None:
            return
        if not self._confirm_cancel(row):
            return
        self.cancelRequested.emit(row.symbol, row.client_order_id)
