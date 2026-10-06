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

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QTableView, QVBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.position_row import (
    PositionRow,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.table_models import (
    PositionsTableModel,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.i_symbol_precisions import (
    ISymbolPrecisions,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.spec_table import SpecTable

_EMPTY_TEXT = "No open positions."


class PositionsPanel(QWidget):  # base-exempt: a container, not a surface
    """@brief The account's open positions, as the platform's own table."""

    #: The selected row changed, or the rows were replaced.
    selectionChanged = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._model = PositionsTableModel(self)
        # Columns, sorting, selection and the empty instruction come from the
        # model's specs (`EPIC-033N`). Symbol ascending is the stable order a
        # user can find a position in; every other column is one click away.
        self._table = SpecTable(
            self._model, object_name="tblPositions", empty_text=_EMPTY_TEXT
        )
        self._table.sort_by(PositionsTableModel.column("symbol"))
        self._table.view.selectionModel().selectionChanged.connect(
            self.selectionChanged
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._table.body)

    def set_rows(self, rows: Sequence[PositionRow]) -> None:
        """Replaces the table's rows entirely — the feed driving this holds
        the whole set (`EPIC-021H`)."""
        self._model.set_rows(rows)
        # A reset clears the selection without a `selectionChanged`.
        self.selectionChanged.emit()

    def use_precisions(self, precisions: ISymbolPrecisions) -> None:
        """Writes prices and sizes in each row's symbol's tick and step."""
        self._model.use_precisions(precisions)

    def add_action(self, action: QAction) -> None:
        """Repeats a host's command in the row's context menu; the command is
        in a menu (`EPIC-033I` stage 3: Trade → Close position)."""
        self._table.view.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)
        self._table.view.addAction(action)

    def selected_row(self) -> PositionRow | None:
        return self._table.selected_row()

    @property
    def table(self) -> QTableView:
        """For a host that needs to size or focus the table itself."""
        return self._table.view
