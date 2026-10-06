"""The Data mode's view (`EPIC-033J`), laid out as HLD §11.2.1 lists it.

- **Central:** the coverage table, one row per stored shard — a symbol at a
  timeframe — with its first and last candle, its count and its health
  (`DatabaseStatusPanel`).
- **Bottom:** the Gaps panel (`GapsPanel`), filled by Data → Check gaps; the
  window's one Output pane shows the mode's `Sync` channel beside it.
- **Status bar:** the stored records and the database size, and a running
  task's progress, in every mode (`IStatusSource`).
- **Dialogs:** Sync history… and Import data… ask which shard
  (`shard_dialogs.py`); Inspect candles shows a shard's candles
  (`KlineInspectorDialog`).

It replaces the Storage Vault page: a hand-styled header, two stat tiles, a
rail of pickers and a date-range card every command read from, a progress
banner with its own Cancel button, and a modal gap inspector. Each became the
platform's part for its job; the view has no style of its own.

The view shows and reports. `selection` is the one record of what is
selected; the commands read it and hand the shard to the coordinators as
they act (`data_command_binding.py`).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDockWidget,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.core.contracts.place import Place
from Sagittarius_Elite_Warrior.src.core.contracts.surface import Surface
from Sagittarius_Elite_Warrior.src.support.ui_kit.constants import (
    CANCELLING_CAPTION,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.output_source_view import (
    OutputSourceView,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.status_readout import status_readout
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import BYTES_KEY
from Sagittarius_Elite_Warrior.src.support.ui_kit.workbench_surface import (
    WorkbenchSurface,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import ColumnKind, ColumnSpec
from sagittarius_engine.extensions.pyside_mvc.workbench.output_pane import OutputChannel

from .data_management_widgets.database_status_panel import DatabaseStatusPanel
from .data_management_widgets.gaps_panel import GapRow, GapsPanel, gap_report
from .data_management_widgets.kline_inspector_dialog import KlineInspectorDialog
from .data_management_widgets.shard_dialogs import (
    ImportDataDialog,
    ShardChoice,
    SyncChoice,
    SyncHistoryDialog,
)

if TYPE_CHECKING:
    from .data_management_view_model import DataManagementViewModel
    from .database_status_table_model import DatabaseStatusRow

#: This mode's surface. Declared here because a module may not import
#: `shell/`; `test_data_mode_view.py` holds it equal to `shell/surfaces.py`'s
#: `data_management` entry.
DATA_SURFACE = Surface(
    "data_management",
    owner="market_data",
    accepts=frozenset({Place.WORKSPACE, Place.CONSOLE}),
)

_CANCELLING_MODE = "CANCELLING"

#: The stat tiles of the status bar, each a one-row read-out; the size's key
#: tells the formatter its value is bytes.
_RECORDS_ROW = "records"
_RECORDS_SPECS = (ColumnSpec(_RECORDS_ROW, "Records", ColumnKind.QUANTITY),)
_SIZE_SPECS = (ColumnSpec(BYTES_KEY, "Database", ColumnKind.QUANTITY),)


class DataSelection(QObject):
    """What the Data commands act on: the selected shard and gap."""

    changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._shard: DatabaseStatusRow | None = None
        self._gap: GapRow | None = None
        self._gaps_listed = False

    @property
    def shard(self) -> DatabaseStatusRow | None:
        return self._shard

    @property
    def gap(self) -> GapRow | None:
        return self._gap

    @property
    def gaps_listed(self) -> bool:
        return self._gaps_listed

    def select_shard(self, shard: DatabaseStatusRow | None) -> None:
        self._shard = shard
        self.changed.emit()

    def select_gap(self, gap: GapRow | None) -> None:
        self._gap = gap
        self.changed.emit()

    def list_gaps(self, listed: bool) -> None:
        self._gaps_listed = listed
        self.changed.emit()


class DataManagementView(OutputSourceView):
    """@brief The coverage table above the Gaps panel."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view_model: DataManagementViewModel | None = None
        self.selection = DataSelection(self)
        self.gaps = GapsPanel()
        self._status_panel: DatabaseStatusPanel | None = None
        self._kline_inspector: KlineInspectorDialog | None = None
        self._records = status_readout(_RECORDS_SPECS)
        self._records.setObjectName("frmStoredRecords")
        self._size = status_readout(_SIZE_SPECS)
        self._size.setObjectName("frmDatabaseSize")
        for readout in (self._records, self._size):
            # Hidden until its figure is known: a title with no value reads
            # as a label beside nothing (review of PR #389). Parented here so
            # showing it before the status bar takes it opens no window.
            readout.setParent(self)
            readout.hide()
        self._task = QLabel()
        self._task.setObjectName("lblDataTask")
        self._progress = QProgressBar()
        self._progress.setObjectName("prgDataTask")
        self._progress.setTextVisible(False)
        self._task.hide()
        self._progress.hide()
        self._central = QWidget()
        self._central_layout = QVBoxLayout(self._central)
        self._surface = WorkbenchSurface(DATA_SURFACE)
        self._surface.place_widget(Place.WORKSPACE, self._central)
        self._surface.place_widget(Place.CONSOLE, self.gaps, title="Gaps")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._surface)
        self.gaps.gapSelected.connect(self.selection.select_gap)

    # -- wiring ---------------------------------------------------------------

    def set_view_model(self, view_model: DataManagementViewModel) -> None:
        self._view_model = view_model
        self._output = OutputChannel("data.sync", "Sync", view_model.logModel)
        if self._status_panel is None:
            self._status_panel = DatabaseStatusPanel(view_model.status_model)
            self._status_panel.rowActionRequested.connect(self._on_row_action)
            self._status_panel.shardSelected.connect(self._on_shard_selected)
            self._central_layout.addWidget(self._status_panel)
        view_model.knownShardCountChanged.connect(
            lambda: self._status_panel.set_known_shard_count(view_model.knownShardCount)
        )
        view_model.openKlineInspectorRequested.connect(self._open_kline_inspector)
        view_model.openGapInspectorRequested.connect(self._show_gaps)
        view_model.progressChanged.connect(self._sync_progress)
        view_model.statsChanged.connect(self._sync_stats)
        view_model.uiModeChanged.connect(self._sync_ui_mode)
        self._sync_stats()
        self._sync_ui_mode()

    def apply_ui_mode(self, mode, section_key: str = "main") -> None:
        """The presenter's FSM state, forwarded to the view model's `uiMode`
        (`BasePresenter._bind_fsm_to_ui` calls this by name)."""
        if self._view_model is None:
            return
        mode_value = getattr(mode, "value", mode)
        self._view_model.set_ui_mode(str(mode_value))

    # -- IStatusSource ------------------------------------------------------

    def status_widgets(self) -> Sequence[QWidget]:
        return (self._records, self._size, self._task, self._progress)

    # -- what the commands ask --------------------------------------------------

    def ask_sync_history(
        self, symbols: Sequence[str], intervals: Sequence[str], current: ShardChoice
    ) -> SyncChoice | None:
        dialog = SyncHistoryDialog(symbols, intervals, current, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialog.choice()

    def ask_import_shard(
        self, symbols: Sequence[str], intervals: Sequence[str], current: ShardChoice
    ) -> ShardChoice | None:
        dialog = ImportDataDialog(symbols, intervals, current, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialog.choice()

    # -- what the view shows ----------------------------------------------------

    @property
    def status_panel(self) -> DatabaseStatusPanel | None:
        return self._status_panel

    @property
    def gaps_dock(self) -> QDockWidget:
        for dock in self._surface.findChildren(QDockWidget):
            if dock.widget() is self.gaps:
                return dock
        raise LookupError("the surface placed no Gaps dock")

    def confirm_delete(self, row: DatabaseStatusRow) -> bool:
        """Data → Delete data's question: the coverage table's, which names
        the shard and its candles."""
        return self._status_panel is not None and self._status_panel.confirm_clear(row)

    def _on_shard_selected(self, row: DatabaseStatusRow | None) -> None:
        self.selection.select_shard(row)

    def _on_row_action(self, action: str, symbol: str, interval: str) -> None:
        """The table's context menu, to the same requests as the menu."""
        if self._view_model is None:
            return
        request = {
            "klines": self._view_model.requestInspectKlines,
            "gaps": self._view_model.requestInspectGaps,
            "clear": self._view_model.requestClearRow,
        }.get(action)
        if request is not None:
            request(symbol, interval)

    def _show_gaps(self) -> None:
        vm = self._view_model
        if vm is None:
            return
        self.gaps.show_report(
            gap_report(
                vm.gapInspectorSymbol,
                vm.gapInspectorInterval,
                vm.gapInspectorTotalMissing,
                vm.gapInspectorCoveragePct,
                vm.gapList,
            )
        )
        self.selection.list_gaps(bool(vm.gapList))
        dock = self.gaps_dock
        dock.show()
        dock.raise_()

    def _open_kline_inspector(self) -> None:
        if self._view_model is None:
            return
        if self._kline_inspector is None:
            self._kline_inspector = KlineInspectorDialog(self._view_model, parent=self)
        self._kline_inspector.open_dialog()

    def _sync_stats(self) -> None:
        vm = self._view_model
        if vm is None:
            return
        self._records.set_values({_RECORDS_ROW: vm.storedRecords})
        self._records.setHidden(vm.storedRecords is None)
        self._size.set_values({BYTES_KEY: vm.databaseSize})
        self._size.setHidden(vm.databaseSize is None)

    def _sync_progress(self) -> None:
        """A running task's progress in the status bar (`ui-presentation-rule.md`
        §10: modeless progress is shown there); Data → Stop stops it."""
        vm = self._view_model
        if vm is None:
            return
        visible = vm.progressVisible
        self._task.setVisible(visible)
        self._progress.setVisible(visible)
        if vm.uiMode == _CANCELLING_MODE:
            self._task.setText(CANCELLING_CAPTION)
            self._progress.setRange(0, 0)
            return
        self._task.setText(vm.progressText)
        if vm.progressMaximum <= 0:
            self._progress.setRange(0, 0)
            return
        self._progress.setRange(0, 100)
        self._progress.setValue(round(vm.progressPercent))

    def _sync_ui_mode(self) -> None:
        vm = self._view_model
        if vm is None:
            return
        self._sync_progress()
        if self._status_panel is not None:
            self._status_panel.set_actions_enabled(vm.uiMode == "IDLE")
