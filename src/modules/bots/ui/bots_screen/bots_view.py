"""`EPIC-033K` — the Bots mode, laid out as HLD §11.2.1 lists it.

The centre has two tabs (`EPIC-040E`): Live, the selected bot's chart, and
Backtest, the sandbox of its parameters (`ui/backtest_workbench/`). Bots (the
list) is docked on the left, Strategies (a row per venue's armed strategy,
`EPIC-033K` stage 3) under it, Plan (the bot's figures, the kind's editor and its
verdicts) on the right, and Orders, Ladder, Fills and Log are tabbed at the
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

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from PySide6.QtCore import QItemSelectionModel, Qt, Signal
from PySide6.QtWidgets import (
    QLabel,
    QTabWidget,
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
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_ladder_panel import (
    BotLadderPanel,
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
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.identity_strip import (
    IdentityStrip,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.selected_bot_precisions import (
    SelectedBotPrecisions,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.bot_kind_panel import (
    BotKindPanel,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.strategies.strategy_rows import (
    STRATEGIES_DOCK,
    StrategiesPanel,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.empty_page import empty_page
from Sagittarius_Elite_Warrior.src.support.ui_kit.i_symbol_precisions import (
    ISymbolPrecisions,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.minimum_hint_slot import (
    MinimumHintSlot,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.plain_label import plain_label
from Sagittarius_Elite_Warrior.src.support.ui_kit.services.display_timezone_preference import (
    DisplayTimezonePreference,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.spec_table import SpecTable
from Sagittarius_Elite_Warrior.src.support.ui_kit.workbench_surface import (
    WorkbenchSurface,
)
from sagittarius_engine.extensions.pyside_mvc import BaseView

from .widget_slot import held_in, replace_in

_EMPTY_TEXT = "No bots yet. Create one with Bots → New bot…."
NO_CHART_TEXT = "Select a bot in Bots to see its chart."
NO_BACKTEST_TEXT = "The selected bot's kind has no backtest."
NO_SELECTION_BACKTEST_TEXT = "Select a bot in Bots to backtest its parameters."

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
#: `BOT-193`: the Grid bot's ladder, beside its orders.
LADDER_DOCK = "Ladder"
FILLS_DOCK = "Fills"
LOG_DOCK = "Log"
#: The centre's two tabs (`EPIC-040E`): the bot's chart, and the sandbox of its parameters.
LIVE_TAB = "Live"
BACKTEST_TAB = "Backtest"


def _note(text: str, name: str) -> QLabel:
    """An instruction a slot shows while it has nothing else, deleted when the slot gives it up
    (`widget_slot.replace_in`)."""
    note = empty_page(text, name)
    note.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    return note


@dataclass(frozen=True, slots=True)
class TabAvailability:
    """Whether the Backtest tab can be used, and if not, why (its tooltip and its page)."""

    enabled: bool = True
    reason: str = ""


class BotsView(BaseView):
    """@brief The Bots mode: the bot's chart and backtest amid its list, plan and activity."""

    #: Whether the Backtest tab can be used, as the host last said (`EPIC-040E`).
    backtest_enabled_changed = Signal(bool)
    #: What the centre shows in front changed: the tab, or the chart or the page in a tab
    #: (`EPIC-040` F1: the chart commands follow it).
    front_chart_changed = Signal()

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
        self.status = plain_label()
        self.status.setObjectName("lblBotsStatus")
        self.status.setWordWrap(True)
        self.status.hide()
        self.plan = BotPlanPanel(self.model)
        self.identity = IdentityStrip(self.model)
        self.strategies = StrategiesPanel()
        self.orders = BotOrdersPanel(self.model)
        self.ladder = BotLadderPanel(self.model)
        # Asks for its minimum only, like the Strategies panel: the tallest bottom panel sets the
        # dock area's height, and the chart keeps the larger share (`BOT-193`).
        self._ladder_slot = MinimumHintSlot(self.ladder)
        self.fills = BotFillsPanel(self.model)
        self.log = BotLogPanel(self.model)
        self.chart_area = QWidget()
        self.chart_area.setObjectName("areaBotChart")
        #: Why no grid is drawn, above the chart (`EPIC-035N`).
        self.chart_note = plain_label()
        self.chart_note.setObjectName("lblGridNotDrawn")
        self.chart_note.setWordWrap(True)
        self.chart_note.setVisible(False)
        chart_column = QVBoxLayout(self.chart_area)
        chart_column.setContentsMargins(0, 0, 0, 0)
        chart_column.addWidget(self.chart_note)
        self._chart_slot = QVBoxLayout()
        self._chart_slot.setContentsMargins(0, 0, 0, 0)
        chart_column.addLayout(self._chart_slot, 1)
        self.backtest = QWidget()
        self.backtest.setObjectName("panelBotBacktest")
        self._backtest_slot = QVBoxLayout(self.backtest)
        self._backtest_slot.setContentsMargins(0, 0, 0, 0)
        self.backtest_enabled = True
        #: Live and Backtest: one stock tab widget, each tab the full width (`EPIC-040E`).
        self.centre = QTabWidget()
        self.centre.setObjectName("tabBotsCentre")
        self.centre.addTab(self.chart_area, LIVE_TAB)
        self.centre.addTab(self.backtest, BACKTEST_TAB)
        self._kind_panel: BotKindPanel | None = None
        self._mode = BotsUiState.NO_SELECTION
        self.surface = WorkbenchSurface(BOTS_SURFACE)
        self._place()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.identity)
        outer.addWidget(self.surface)
        self.set_chart(None)
        self.set_backtest_page(None, NO_SELECTION_BACKTEST_TEXT)
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

    def use_venue_filters(
        self, filters: Mapping[TradingVenue, ISymbolPrecisions]
    ) -> None:
        """Writes the selected bot's orders and fills in its own venue's
        symbol filters (`EPIC-033N`)."""
        precisions = SelectedBotPrecisions(filters, lambda: self.model.selected)
        self.orders.use_precisions(precisions)
        self.ladder.use_precisions(precisions)
        self.fills.use_precisions(precisions)

    def show_ladder(self) -> None:
        """Brings the Ladder tab to the front of the bottom panels."""
        self.surface.dock_of(self._ladder_slot).raise_()

    def use_display_timezone(self, timezone: DisplayTimezonePreference) -> None:
        """The Fills table reads its Time column in the shared display zone (`BOT-205`); the
        chart's own drop-down sits in its header, built with the chart."""
        self.fills.use_display_timezone(timezone)

    def set_chart(self, chart: QWidget | None) -> None:
        replace_in(self._chart_slot, chart or _note(NO_CHART_TEXT, "lblBotsNoChart"))
        self.front_chart_changed.emit()

    def shown_chart(self) -> QWidget | None:
        """What the Live tab holds: the bot's chart, or the note that stands in for it."""
        return held_in(self._chart_slot)

    def shown_backtest_page(self) -> QWidget | None:
        """What the Backtest tab holds: the venue's workbench page, or a note."""
        return held_in(self._backtest_slot)

    def status_widgets(self) -> Sequence[QWidget]:
        """`IStatusSource`: the selected bot's venue, in the status bar."""
        return (self.identity.status_label,)

    def lock_chart(self, reason: str) -> None:
        """The chart's place says why there is no chart yet (`EPIC-034D`)."""
        replace_in(self._chart_slot, _note(reason, "lblBotsChartLocked"))
        self.front_chart_changed.emit()

    def set_backtest_page(self, page: QWidget | None, note: str) -> None:
        """The workbench of the selected bot's venue; `None` leaves `note` where it would be."""
        replace_in(
            self._backtest_slot,
            page or _note(note or NO_BACKTEST_TEXT, "lblBotsNoBacktest"),
        )
        self.front_chart_changed.emit()

    def set_backtest_available(self, tab: TabAvailability) -> None:
        """The Backtest tab is off, with `tab.reason` as its tooltip, for a bot the workbench
        cannot replay: disabled and never hidden (`ui-presentation-rule.md` §2). A tab turned off
        while shown gives way to Live, as Qt's tab bar does for any tab it turns off."""
        self.centre.setTabEnabled(1, tab.enabled)
        self.centre.setTabToolTip(1, tab.reason)
        if tab.enabled != self.backtest_enabled:
            self.backtest_enabled = tab.enabled
            self.backtest_enabled_changed.emit(tab.enabled)

    def show_live(self) -> None:
        self.centre.setCurrentIndex(0)

    def show_backtest(self) -> None:
        """View → Backtest; a tab that is off stays where it is."""
        if self.backtest_enabled:
            self.centre.setCurrentIndex(1)

    # -- internals -------------------------------------------------------- #

    def _place(self) -> None:
        bots = QWidget()
        bots.setObjectName("panelBots")
        column = QVBoxLayout(bots)
        column.addWidget(self.status)
        column.addWidget(self._bots_table.body, 1)
        surface = self.surface
        surface.place_widget(Place.WORKSPACE, self.centre)
        self._place_left(bots)
        surface.place_widget(Place.RAIL, self.plan, title=PLAN_DOCK)
        for widget, title in (
            (self.orders, ORDERS_DOCK),
            (self._ladder_slot, LADDER_DOCK),
            (self.fills, FILLS_DOCK),
            (self.log, LOG_DOCK),
        ):
            surface.place_widget(Place.CONSOLE, widget, title=title)
        # The bottom docks are tabbed; a bot is watched by its orders first.
        surface.dock_of(self.orders).raise_()

    def _place_left(self, bots: QWidget) -> None:
        """Bots above Strategies, both in view, never tabbed.

        The surface tabs a second panel of one side with the first, and
        tabbed panels on two sides, made before the window first shows,
        leave a stale tab bar drawn over the panels (Qt 6, `EPIC-033I`): the
        bottom is this mode's one tabbed side. So Bots steps out of the left
        side while Strategies is placed, and comes back above it. Both ask
        for no more than their minimum, so they share the column evenly; the
        person drags the splitter, and the layout is remembered.

        The left column runs the mode's full height, beside the bottom
        panels: under it they would add their minimum to the column's, and
        the mode would no longer fit a 1024×700 window (measured: 550 px
        against 500 with a Grid's backtest in front).
        """
        surface = self.surface
        surface.setCorner(
            Qt.Corner.BottomLeftCorner, Qt.DockWidgetArea.LeftDockWidgetArea
        )
        surface.place_widget(Place.NAVIGATOR, bots, title=BOTS_DOCK)
        bots_dock = surface.dock_of(bots)
        surface.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, bots_dock)
        strategies = MinimumHintSlot(self.strategies)
        surface.place_widget(Place.NAVIGATOR, strategies, title=STRATEGIES_DOCK)
        strategies_dock = surface.dock_of(strategies)
        surface.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, bots_dock)
        surface.splitDockWidget(bots_dock, strategies_dock, Qt.Orientation.Vertical)

    def _connect(self) -> None:
        self.model.bots_changed.connect(self._show_bots)
        self.model.selection_changed.connect(self._sync_selection)
        self.model.statusChanged.connect(self._show_status)
        self.model.chart_note_changed.connect(self._show_chart_note)
        self.model.connect_changed.connect(self._lock_plan)
        self.table.selectionModel().selectionChanged.connect(self._on_row_selected)
        self.centre.currentChanged.connect(self.front_chart_changed)

    def _show_chart_note(self) -> None:
        self.chart_note.setText(self.model.chart_note)
        self.chart_note.setVisible(bool(self.model.chart_note))

    def _lock_plan(self) -> None:
        """The Plan waits for the account (`EPIC-034D`, D1)."""
        self.plan.setEnabled(not self.model.connect_view.locked)

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
        message = str(self.model.statusMessage)
        self.status.setText(message)
        self.status.setVisible(bool(message))
