"""`EPIC-033K` — the Bots mode, laid out as HLD §11.2.1 lists it.

The selected bot's chart is the centre; Bots (the list) is docked on the
left, Plan (the bot's figures, the kind's editor and its verdicts) on the
right, and Orders, Fills, Log and the kind's Backtest are tabbed at the
bottom. Every command is an action of the Bots menu (`bots_commands.py`);
nothing here is a push button.

`apply_ui_mode` is the screen's FSM made visible (`bots_ui_fsm_matrix`): the
list locks while an action is in flight, and a bot's parameters are editable
only in the editing mode.

Before `EPIC-033K` the list and a detail shell shared a splitter, the detail a
`QTabWidget` of seven pages: the chart was one tab among the parameters, so
watching a bot and editing its plan were never on screen together.
"""

from __future__ import annotations

from typing import override

from PySide6.QtCore import QItemSelectionModel, QSize
from PySide6.QtWidgets import (
    QLabel,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.core.contracts.place import Place
from Sagittarius_Elite_Warrior.src.core.contracts.surface import Surface
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_activity_panels import (
    BotFillsPanel,
    BotLogPanel,
    BotOrdersPanel,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_plan_panel import (
    BotPlanPanel,
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
from Sagittarius_Elite_Warrior.src.support.ui_kit.spec_table import SpecTable
from Sagittarius_Elite_Warrior.src.support.ui_kit.workbench_surface import (
    WorkbenchSurface,
)
from sagittarius_engine.extensions.pyside_mvc import BaseView

from .widget_slot import replace_in

_EMPTY_TEXT = "No bots yet. Create one with Bots → New bot…."
NO_CHART_TEXT = "Select a bot in Bots to see its chart."
NO_BACKTEST_TEXT = "The selected bot's kind has no backtest."

#: This mode's surface. Declared here because a module may not import
#: `shell/`; `test_bots_view_renders_the_surface_the_shell_declares` holds it
#: equal to `shell/surfaces.py`'s `bots` entry.
BOTS_SURFACE = Surface(
    "bots",
    owner="bots",
    accepts=frozenset({Place.WORKSPACE, Place.NAVIGATOR, Place.RAIL, Place.CONSOLE}),
)
#: The panels HLD §11.2.1 lists for this mode, by their dock titles.
BOTS_DOCK = "Bots"
PLAN_DOCK = "Plan"
ORDERS_DOCK = "Orders"
FILLS_DOCK = "Fills"
LOG_DOCK = "Log"
#: Not in HLD §11.2.1's row: the kind's own backtest (`EPIC-029D`), a tab
#: among the bottom panels, holding an instruction for a kind without one.
BACKTEST_DOCK = "Backtest"


class BotsView(BaseView):
    """@brief The Bots mode: the bot's chart amid its list, plan and activity."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.model = BotsViewModel(self)
        self.bots = BotsTableModel(self)
        # By name, the order a user finds a bot in.
        self._bots_table = SpecTable(
            self.bots, object_name="tblBots", empty_text=_EMPTY_TEXT
        )
        self._bots_table.sort_by(BotsTableModel.column("name"))
        self._proxy = self._bots_table.proxy
        self.table = self._bots_table.view
        self.status = QLabel()
        self.status.setObjectName("lblBotsStatus")
        self.status.setWordWrap(True)
        self.status.hide()
        self.plan = BotPlanPanel(self.model)
        self.orders = BotOrdersPanel(self.model)
        self.fills = BotFillsPanel(self.model)
        self.log = BotLogPanel(self.model)
        self.chart_area = QWidget()
        self.chart_area.setObjectName("areaBotChart")
        self._chart_slot = QVBoxLayout(self.chart_area)
        self._chart_slot.setContentsMargins(0, 0, 0, 0)
        self.backtest = _BacktestSlot()
        self.backtest.setObjectName("panelBotBacktest")
        self._backtest_slot = QVBoxLayout(self.backtest)
        self._kind_panel: BotKindPanel | None = None
        self._mode = BotsUiState.NO_SELECTION
        self.surface = WorkbenchSurface(BOTS_SURFACE)
        self._place()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.surface)
        self.set_chart(None)
        self.set_backtest_page(None)
        self._connect()

    def apply_ui_mode(self, state: BotsUiState, section_key: str | None = None) -> None:
        """The presenter's FSM, made visible (`BasePresenter._bind_fsm_to_ui`)."""
        self._mode = state
        self.table.setEnabled(state is not BotsUiState.ACTION_IN_FLIGHT)
        if self._kind_panel is not None:
            self._kind_panel.set_editable(state is BotsUiState.EDITING_DRAFT)

    def set_kind_panel(self, panel: BotKindPanel | None) -> None:
        self._kind_panel = panel
        self.plan.set_kind_panel(panel)
        if panel is not None:
            panel.set_editable(self._mode is BotsUiState.EDITING_DRAFT)

    def set_chart(self, chart: QWidget | None) -> None:
        replace_in(self._chart_slot, chart or _note(NO_CHART_TEXT))

    def set_backtest_page(self, page: QWidget | None) -> None:
        """The kind's backtest page; `None` leaves the instruction."""
        replace_in(self._backtest_slot, page or _note(NO_BACKTEST_TEXT))

    # -- internals -------------------------------------------------------- #

    def _place(self) -> None:
        bots = QWidget()
        bots.setObjectName("panelBots")
        column = QVBoxLayout(bots)
        column.addWidget(self.status)
        column.addWidget(self._bots_table.body, 1)
        surface = self.surface
        surface.place_widget(Place.WORKSPACE, self.chart_area)
        surface.place_widget(Place.NAVIGATOR, bots, title=BOTS_DOCK)
        surface.place_widget(Place.RAIL, self.plan, title=PLAN_DOCK)
        for widget, title in (
            (self.orders, ORDERS_DOCK),
            (self.fills, FILLS_DOCK),
            (self.log, LOG_DOCK),
            (self.backtest, BACKTEST_DOCK),
        ):
            surface.place_widget(Place.CONSOLE, widget, title=title)
        # The bottom docks are tabbed; a bot is watched by its orders first.
        surface.dock_of(self.orders).raise_()

    def _connect(self) -> None:
        self.model.bots_changed.connect(self._show_bots)
        self.model.selection_changed.connect(self._sync_selection)
        self.model.statusChanged.connect(self._show_status)
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
        self.status.setText(message)
        self.status.setVisible(bool(message))


class _BacktestSlot(QWidget):
    """The Backtest panel's content: it asks the dock area for no more than
    its minimum. A kind's backtest page holds charts whose own size hints run
    to a thousand pixels (the Grid's: 850×1104), and the bottom docks take the
    largest hint among them, so one tab left the chart 104 of 768 px (the
    PR #361 review). The person still drags the dock taller."""

    @override
    def sizeHint(self) -> QSize:
        return self.minimumSizeHint()


def _note(text: str) -> QLabel:
    note = QLabel(text)
    note.setWordWrap(True)
    return note
