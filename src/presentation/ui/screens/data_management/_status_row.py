"""One row of the Data Management status list."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QModelIndex
from PySide6.QtWidgets import (
    QWidget,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import (
    DataRow,
    RowAction,
    StyleRole,
    Tone,
    WidgetState,
    apply_role,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.database_status_table_model import (
    DatabaseStatusTableModel,
)

from ._status_columns import _ACTIONS_COLUMN, _STATUS_COLUMNS

if TYPE_CHECKING:
    from .data_management_view_model import DataManagementViewModel


_STATUS_ACTIONS = (
    RowAction("KLines"),
    RowAction("Gaps"),
    RowAction("Sync"),
    RowAction("Clear"),
)

_ACTION_TONES = {2: Tone.POSITIVE, 3: Tone.NEGATIVE}

_KLINES_ACTION, _GAPS_ACTION, _SYNC_ACTION, _CLEAR_ACTION = range(4)

_ACTION_OBJECT_NAMES = {
    _KLINES_ACTION: "btnRowInspectKlines",
    _GAPS_ACTION: "btnRowInspect",
    _SYNC_ACTION: "btnRowSync",
    _CLEAR_ACTION: "btnRowClear",
}

(
    _SYMBOL_CELL,
    _INTERVAL_CELL,
    _FIRST_RECORD_CELL,
    _LAST_RECORD_CELL,
    _TOTAL_CELL,
    _STATUS_CELL,
) = range(len(_STATUS_COLUMNS))


class _StatusRowWidget(DataRow):
    """One row of the status table, on the engine's `DataRow`.

    Still driven through `QListView.setIndexWidget()` rather than a
    `TableCard`: the source model (`DatabaseStatusTableModel`) is a
    single-column, multi-role table — its own docstring says it "exposes
    named roles so QML delegates address fields by role name" — and turning
    that into a real N-column `QAbstractTableModel` would change a model
    this migration is not supposed to touch. `DataRow` replaces the
    delegate's *rendering*; the list keeps driving it.
    """

    def __init__(
        self,
        view_model: DataManagementViewModel,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            _STATUS_COLUMNS,
            actions=_STATUS_ACTIONS,
            action_stretch=_ACTIONS_COLUMN.stretch,
            parent=parent,
        )
        self._view_model = view_model
        self._symbol = ""
        self._interval = "1m"

        # The 8px inset the heading strip above uses, so cells sit under
        # their headings. `DataRow` itself draws no padding — the table
        # around a row owns that, and here the table is a `QListView`.
        self.layout().setContentsMargins(8, 0, 8, 0)
        self.layout().setSpacing(6)

        self.set_cell_role(_SYMBOL_CELL, StyleRole.TABLE_CELL_STRONG)
        # `SELECTED` is the badge's emphasised form — accent text on an
        # accent border, which is what this pill has always been. The
        # unemphasised form is muted, and a timeframe is not a quiet detail
        # here: it is half of what identifies the row.
        apply_role(
            self.cell(_INTERVAL_CELL), StyleRole.BADGE, state=WidgetState.SELECTED
        )
        self.set_cell_role(_FIRST_RECORD_CELL, StyleRole.CAPTION)
        self.set_cell_role(_LAST_RECORD_CELL, StyleRole.CAPTION)
        self.set_cell_role(_STATUS_CELL, StyleRole.TABLE_CELL_STRONG)
        for position, tone in _ACTION_TONES.items():
            self.set_action_tone(position, tone)

        self.action_triggered.connect(self._on_action)

    def _on_action(self, position: int) -> None:
        request = {
            _KLINES_ACTION: self._view_model.requestInspectKlines,
            _GAPS_ACTION: self._view_model.requestInspectGaps,
            _SYNC_ACTION: self._view_model.requestSyncRow,
            _CLEAR_ACTION: self._view_model.requestClearRow,
        }[position]
        request(self._symbol, self._interval)

    def apply_row(self, index: QModelIndex) -> None:
        # `index.model()` is DatabaseStatusFilterProxy (a plain
        # QSortFilterProxyModel), which has no role constants of its own —
        # the source model's roles pass through proxy indexes unchanged, so
        # DatabaseStatusTableModel's constants are used directly here.
        model = index.model()
        model_roles = DatabaseStatusTableModel
        self._symbol = model.data(index, model_roles.SymbolRole) or ""
        self._interval = model.data(index, model_roles.IntervalRole) or "1m"
        is_healthy = bool(model.data(index, model_roles.IsHealthyRole))

        self.set_cells(
            [
                self._symbol,
                self._interval,
                str(model.data(index, model_roles.FirstRecordRole) or ""),
                str(model.data(index, model_roles.LastRecordRole) or ""),
                str(model.data(index, model_roles.TotalCandlesRole) or ""),
                str(model.data(index, model_roles.StatusTextRole) or ""),
            ]
        )
        self.setObjectName(
            f"statusRow_{self._symbol}_{self._interval}"
        )  # not a public contract, but useful for debugging
        self.set_cell_role(_STATUS_CELL, StyleRole.TABLE_CELL_STRONG)
        self.set_cell_tone(_STATUS_CELL, Tone.POSITIVE if is_healthy else Tone.NEGATIVE)
        self.set_action_visible(_GAPS_ACTION, not is_healthy)

        for position, name in _ACTION_OBJECT_NAMES.items():
            self.action_buttons[position].setObjectName(
                f"{name}_{self._symbol}_{self._interval}"
            )

    def apply_ui_mode(self, idle: bool) -> None:
        for button in self.action_buttons:
            button.setEnabled(idle)
