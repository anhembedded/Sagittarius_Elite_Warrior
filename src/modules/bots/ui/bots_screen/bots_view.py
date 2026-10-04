"""`EPIC-029F` — the Bots screen: the list of bots beside one bot's detail.

`apply_ui_mode` is the screen's FSM made visible (`bots_ui_fsm_matrix`): the
list and New bot lock while an action is in flight, and a bot's parameters
are editable only in the editing mode.

A workbench host from birth (`ui-presentation-rule.md`, `EPIC-033`): the screen
is a `WorkbenchSurface` (a `QMainWindow` on the Engine's `RegionHost`, as the
Welcome surface is) whose workspace holds New bot, the status line and the
list beside the detail. Stock controls, no style sheet. `EPIC-033K` (Strategies
mode) re-lays it out on the shell's workbench.
"""

from __future__ import annotations

from PySide6.QtCore import QItemSelectionModel, QSortFilterProxyModel, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.core.contracts.place import Place
from Sagittarius_Elite_Warrior.src.core.contracts.surface import Surface
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_detail_panel import (
    BotDetailPanel,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_table_models import (
    BotsTableModel,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_ui_fsm_matrix import (
    BotsUiState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view_model import (
    BotsViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.bot_kind_panel import (
    BotKindPanel,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.table_model import SORT_ROLE
from Sagittarius_Elite_Warrior.src.support.ui_kit.workbench_surface import (
    WorkbenchSurface,
)
from sagittarius_engine.extensions.pyside_mvc import BaseView

#: This screen's surface. Declared here because a module may not import
#: `shell/`; `test_bots_view_renders_the_surface_the_shell_declares` holds it
#: equal to `shell/surfaces.py`'s `bots` entry, as the Dev Board's is.
BOTS_SURFACE = Surface("bots", owner="bots", accepts=frozenset({Place.WORKSPACE}))


class BotsView(BaseView):
    """@brief The list of bots and the selected bot's detail."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.model = BotsViewModel(self)
        self.bots = BotsTableModel(self)
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self.bots)
        self._proxy.setSortRole(SORT_ROLE)
        self.table = self._build_bots_table()
        self.new_bot = QPushButton("New bot")
        self.new_bot.setObjectName("btnNewBot")
        self.detail = BotDetailPanel(self.model)
        self._kind_panel: BotKindPanel | None = None
        self._mode = BotsUiState.NO_SELECTION
        self._status = QLabel()
        self._status.setObjectName("lblBotsStatus")
        self._status.setWordWrap(True)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.table)
        splitter.addWidget(self.detail)
        splitter.setStretchFactor(1, 2)
        self._status.hide()
        commands = QHBoxLayout()
        commands.addWidget(self.new_bot)
        commands.addStretch(1)
        workspace = QWidget()
        column = QVBoxLayout(workspace)
        column.addLayout(commands)
        column.addWidget(self._status)
        column.addWidget(splitter, 1)
        self._surface = WorkbenchSurface(BOTS_SURFACE)
        self._surface.place_widget(Place.WORKSPACE, workspace)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._surface)
        self._connect()

    def apply_ui_mode(self, state: BotsUiState, section_key: str | None = None) -> None:
        """The presenter's FSM, made visible (`BasePresenter._bind_fsm_to_ui`)."""
        self._mode = state
        busy = state is BotsUiState.ACTION_IN_FLIGHT
        self.table.setEnabled(not busy)
        self.new_bot.setEnabled(not busy)
        self.new_bot.setToolTip("Another action is still running." if busy else "")
        self.detail.lock_actions(busy)
        if self._kind_panel is not None:
            self._kind_panel.set_editable(state is BotsUiState.EDITING_DRAFT)

    def set_kind_panel(self, panel: BotKindPanel | None) -> None:
        self._kind_panel = panel
        self.detail.set_kind_panel(panel)
        if panel is not None:
            panel.set_editable(self._mode is BotsUiState.EDITING_DRAFT)

    def set_chart(self, chart: QWidget | None) -> None:
        self.detail.set_chart(chart)

    # -- internals -------------------------------------------------------- #

    def _build_bots_table(self) -> QTableView:
        table = QTableView()
        table.setObjectName("tblBots")
        table.setModel(self._proxy)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSortingEnabled(True)
        table.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        return table

    def _connect(self) -> None:
        self.model.bots_changed.connect(self._show_bots)
        self.model.selection_changed.connect(self._sync_selection)
        self.model.statusChanged.connect(self._show_status)
        self.new_bot.clicked.connect(self.model.new_bot_requested)
        self.table.selectionModel().selectionChanged.connect(self._on_row_selected)

    def _show_bots(self) -> None:
        """A reset drops the selection; it is put back on the same bot,
        silently, so re-reading the list never reads as the user picking."""
        selection = self.table.selectionModel()
        selection.blockSignals(True)
        self.bots.set_rows(self.model.bots)
        selection.blockSignals(False)
        self._sync_selection()

    def _sync_selection(self) -> None:
        selected = self.model.selected
        selection = self.table.selectionModel()
        row = self.bots.row_index_of(selected.bot_id) if selected is not None else -1
        if row < 0:
            selection.blockSignals(True)
            selection.clearSelection()
            selection.blockSignals(False)
            return
        index = self._proxy.mapFromSource(self.bots.index(row, 0))
        selection.blockSignals(True)
        selection.select(
            index,
            QItemSelectionModel.SelectionFlag.ClearAndSelect
            | QItemSelectionModel.SelectionFlag.Rows,
        )
        selection.blockSignals(False)

    def _on_row_selected(self, *_args: object) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            self.model.select_requested.emit("")
            return
        row = self.bots.row_for(self._proxy.mapToSource(rows[0]))
        self.model.select_requested.emit(row.bot_id if row is not None else "")

    def _show_status(self) -> None:
        message = str(self.model.property("statusMessage"))
        self._status.setText(message)
        self._status.setVisible(bool(message))
