"""The K-line inspector — a real `QDialog` over the stored candles.

**What this replaces.** `KlineInspectorTable.qml` + `KlineInspectorRow.qml`
hosted in a `QmlOverlay`: a hand-drawn modal (its own title bar, its own
close affordance, its own table) where the platform has `QDialog` and
`QTableView`. ADR D20/D22 and the Familiarity principle both say not to
redraw one of those.

**One thing the user gets that the QML modal did not have**, because the rule
asks for it rather than because the rebuild allowed it: **a Close button**.
`HLD §11.5` — every dialog has Cancel or Close. The QML version left only the
window's own close control and Escape, which its docstring recorded as a
deliberate carry-over of the even older dialog's behaviour. On a real
`QDialog` the standard `QDialogButtonBox` supplies it, wired to Escape as
well, so there is nothing to invent.

**Sorting is switched off on purpose**, unlike the status table's. A candle
series is ordered by time, and that order is the data: the row above a candle
is the minute before it. Letting a click on "Close" reshuffle the series would
make every neighbouring row a coincidence.

**What is still missing, and is named rather than dropped:** jump-to-date.
`KLineInspectorTableModel` used to carry a `jump_to_date()` that computed a
page number, and no widget has called it since the QML port removed
pagination in `EPIC-015`. Rebuilding it here would mean designing a feature,
not migrating one, so it stays out of PR 0.4b and is recorded as an open
question in the epic's Phase 0 document,
`Tasks/epics/EPIC-025_module_theo_bounded_context/incomplete/EPIC-025A_phase0_mechanism_and_market_data.md`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from ..kline_inspector_table_model import KLineInspectorTableModel

if TYPE_CHECKING:
    from ..data_management_view_model import DataManagementViewModel

_DIALOG_TITLE = "Candle Data Lookup (KLine Inspector)"
_INITIAL_SIZE = (900, 620)


class KlineInspectorDialog(QDialog):  # base-exempt: ADR D22, a dialog is a QDialog
    """
    @brief Data Management's candle-lookup dialog for one symbol/interval.

    @details Derives `QDialog` rather than the kit's `Overlay`, and the
    `base-exempt` marker above says why: `Overlay` *is* the hand-drawn modal
    this replaces. The ratchet that marker answers predates ADR D20–D22 and
    was pulling in the opposite direction (`EPIC-007F`: inherit the kit's
    `Card`/`Panel`/`Overlay`); the ADR reversed it for new desktop widgets.

    @details Binds the screen's own `KLineInspectorTableModel` — the same
    instance `DataManagementViewModel.set_kline_inspector_data()` fills — so
    opening the dialog shows whatever the last fetch landed, with no second
    copy of the candle list anywhere.
    """

    def __init__(
        self, view_model: DataManagementViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self.setObjectName("klineInspectorDialog")
        self.setWindowTitle(_DIALOG_TITLE)
        self.setModal(True)
        self.resize(*_INITIAL_SIZE)

        self._subtitle = QLabel()
        self._subtitle.setObjectName("lblKlineInspectorSubtitle")
        self._empty = QLabel("No candle data available in the database.")
        self._empty.setObjectName("lblKlineInspectorEmpty")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table = self._build_table(view_model.kline_inspector_model)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.setObjectName("klineInspectorButtons")
        # `rejected` rather than a hand-wired `clicked`: it is the signal
        # Escape emits too, so both close paths run the same code.
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self._subtitle)
        layout.addWidget(self._table, 1)
        layout.addWidget(self._empty, 1)
        layout.addWidget(buttons)

        self.refresh()

    def _build_table(self, model: KLineInspectorTableModel) -> QTableView:
        table = QTableView()
        table.setObjectName("tblKlineInspector")
        table.setModel(model)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.setWordWrap(False)
        table.setSortingEnabled(False)
        table.verticalHeader().setVisible(False)
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(
            KLineInspectorTableModel.TIME_COLUMN, QHeaderView.ResizeMode.Stretch
        )
        return table

    def refresh(self) -> None:
        """Re-reads the subtitle and the empty state from the view model.

        The table itself needs nothing: `set_klines()` resets the model the
        view is already bound to.
        """
        vm = self._view_model
        candles = vm.kline_inspector_model.total_records
        self._subtitle.setText(
            f"{vm.klineInspectorSymbol} ({vm.klineInspectorInterval})  •  "
            f"{candles} candle{'' if candles == 1 else 's'}"
        )
        self._table.setVisible(candles > 0)
        self._empty.setVisible(candles == 0)

    def open_dialog(self) -> None:
        """Opens the dialog on the current candle list.

        `set_kline_inspector_data` — which fires `openKlineInspectorRequested`,
        the one signal this dialog opens from — always means fresh data
        landed, so the subtitle is re-read every time.
        """
        self.refresh()
        self.show()
        self.raise_()
