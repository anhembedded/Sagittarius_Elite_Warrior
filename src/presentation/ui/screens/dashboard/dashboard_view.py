from PySide6.QtCore import Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QLabel, QToolButton, QVBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.core.contracts.place import Place
from Sagittarius_Elite_Warrior.src.core.contracts.surface import Surface
from Sagittarius_Elite_Warrior.src.presentation.ui.components.order_book.open_order_row import (
    OpenOrderRow,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.order_book.open_orders_panel import (
    OpenOrdersPanel,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.order_book.position_row import (
    PositionRow,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.order_book.positions_panel import (
    PositionsPanel,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card import (
    ChartCard,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.timeframe_pin_preferences import (
    TimeframePinPreferences,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import (
    PreferredHeightScrollArea,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.surface_building import (
    fill_surface,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.workbench_surface import (
    WorkbenchSurface,
)
from sagittarius_engine.extensions.pyside_mvc import BaseView

from .dev_board_panel import MANUAL_ORDER_DIALOG, DevBoardPanel

_TITLE = "Developer Board (Live Testbed)"
_SUBTITLE = "Test indicators & scripts on live data"

#: `EPIC-023B` — the equity chart's `ChartCard(symbol=...)` title, same
#: constant `TradingView` uses for its own equity chart.
_EQUITY_CHART_TITLE = "Equity"

#: An empty `ChartCard`'s own `sizeHint()` is tiny — no candles and no toolbar
#: to size around — so without a floor it opens as a sliver with cramped axis
#: labels (user-reported). Inside a dock the user can drag it to any height
#: from there, and the perspective remembers it; this only decides where it
#: starts.
_EQUITY_CHART_MINIMUM_HEIGHT = 220

#: Dock titles this View owns. A title is the user's handle on a panel — what
#: the View menu lists, what a floating panel's title bar reads, and what
#: `saveState()` keys a dock by, so renaming one drops that panel out of every
#: perspective saved before the rename. The controls' own five titles belong to
#: `DevBoardPanel`, which builds those cards.
POSITIONS_DOCK = "Positions"
OPEN_ORDERS_DOCK = "Open orders"
EQUITY_DOCK = "Equity"
MONITOR_DOCK = "System monitor"

#: This screen's surface, declared here because a file under `presentation/`
#: may not import `shell/` — the shell is *Main*, so depending on it is a
#: cycle — and `shell/surfaces.py` is where the application's list lives. Not
#: a second source of truth:
#: `test_dashboard_view.py::test_the_view_renders_the_surface_the_shell_declares`
#: asserts this equals that list's `dev_board` entry. The declaration goes
#: when this screen moves into a module's `ui/`, where a factory is handed the
#: container and can ask `IContributionTable` for it.
DEV_BOARD_SURFACE = Surface(
    "dev_board",
    owner="shell",
    accepts=frozenset(
        {
            Place.HEADER,
            Place.CONTEXT_BAR,
            Place.WORKSPACE,
            Place.RAIL,
            Place.CONSOLE,
            Place.MODAL,
            Place.STATUS_TILE,
            Place.DEV_PROBE,
        }
    ),
    gated_by="dev.mode",
)


def _action_button(action: QAction) -> QToolButton:
    """A toolbar button for an action, so the header shows what `F9` does.

    `QToolBar.addWidget` takes widgets and this View hands the host widgets
    rather than actions (`IPlaceHost.place_widget` is a widget contract — a
    module contributes a `QWidget`, not a `QAction`), so the action is wrapped
    rather than added twice. The button keeps the action's text, shortcut hint
    and enabled state, because that is what a `QToolButton` bound to a
    `QAction` does.
    """
    button = QToolButton()
    button.setDefaultAction(action)
    button.setObjectName("btnManualOrder")
    return button


class DashboardView(BaseView):
    """
    @brief The View for the Dev Board Screen — a developer testbed, not the
    app's end-user dashboard.

    @details A **workbench** since `EPIC-025` PR 1.4c-2: one nested
    `QMainWindow` (`WorkbenchSurface`) whose central widget is the scrolling
    column of `ChartCard`s, with everything else in a `QDockWidget` the user
    can move, tab, float, hide and have remembered — Positions, Open orders,
    Equity and the five control cards on the right, the System Monitor log at
    the bottom, the price ticker and websocket pill in the status bar.

    Before it was a `PageShell` holding one `QSplitter`: two fixed panes,
    neither hideable, and a rail column too narrow for a many-column table
    (`BOT-128`) — which is why the two account tables used to sit squeezed
    above the charts instead of beside them.

    PR 1.4c-3 then split the controls: `DevBoardPanel` stopped being a widget
    and became the builder of five cards this View places in five docks, with
    the manual-order card contributed as a **dialog** on `F9` — order entry is
    something the user does occasionally, with input and a confirmation, and as
    a card in a scrolling column it was permanently in the way of everything
    below it (HLD §11.3, and MetaTrader's own F9).

    What did not change: the controls are still built lazily at
    `set_view_model()` time (they need a real ViewModel to construct against),
    the chart column is still QtWidgets/pyqtgraph, and FSM state still reaches
    them through `apply_ui_mode` → the ViewModel's `uiMode` property.
    """

    #: `EPIC-024B` §0 — re-exposes `OpenOrdersPanel.cancelRequested`, same
    #: layered re-export the panel itself does for its own table.
    cancelOrderRequested = Signal(str, str)

    def __init__(self, parent=None, *, contributions=None, container=None):
        super().__init__(parent)
        self._view_model = None
        self._panel: DevBoardPanel | None = None
        # What a *module* contributed to this surface, and what its factories
        # take. `None` for a bare `DashboardView()` — a preview, a unit test —
        # which then renders this screen's own widgets and nothing else.
        self._contributions = contributions
        self._container = container
        # Follow-up to `EPIC-015` Phase 4: self-constructed default so a bare
        # DashboardView() still works unpersisted; DashboardPresenter
        # overrides this with the DI-resolved, shared store via
        # set_timeframe_pin_preferences() in production — same shape and
        # reason as BackTestView's own fallback.
        self._timeframe_pin_preferences = TimeframePinPreferences()
        self._setup_ui()

    def _setup_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        self._surface = WorkbenchSurface(DEV_BOARD_SURFACE)
        outer_layout.addWidget(self._surface)

        # The screen says what it is where a workbench can say it: the context
        # bar. `BOT-014` asked for the Dev Board to label itself a developer
        # testbed, distinct from an end-user dashboard, and a `QMainWindow`
        # has no page-title band to carry that.
        self._identity_label = QLabel(f"{_TITLE} — {_SUBTITLE}")
        self._identity_label.setObjectName("lblDevBoardIdentity")
        self._surface.place_widget(Place.CONTEXT_BAR, self._identity_label)

        # The workspace: the scrolling column of dynamic ChartCards.
        self.scroll_area = PreferredHeightScrollArea()
        self.scroll_area.setWidgetResizable(True)

        self.charts_container = QWidget()
        self.charts_layout = QVBoxLayout(self.charts_container)
        self.charts_layout.setContentsMargins(0, 0, 0, 0)
        self.charts_layout.setSpacing(15)
        # No trailing stretch here: chart cards are added with a stretch factor
        # (see render_symbol_cards) so they expand to fill the available height
        # instead of being squeezed to their minimum size with empty space below.

        self.scroll_area.setWidget(self.charts_container)
        self._surface.place_widget(Place.WORKSPACE, self.scroll_area)

        # `EPIC-023A` — positions and open orders, account-wide, the same
        # widgets `TradingView` embeds (`components/order_book/`). Docks now,
        # each as wide as the user drags it, which is what the old fixed rail
        # column could not offer and HLD §11.2 assigns them.
        self._positions_panel = PositionsPanel()
        self._positions_panel.setObjectName("positionsPanel")
        self._surface.place_widget(
            Place.RAIL, self._positions_panel, title=POSITIONS_DOCK
        )

        self._open_orders_panel = OpenOrdersPanel()
        self._open_orders_panel.setObjectName("openOrdersPanel")
        self._open_orders_panel.cancelRequested.connect(self.cancelOrderRequested)
        self._surface.place_widget(
            Place.RAIL, self._open_orders_panel, title=OPEN_ORDERS_DOCK
        )

        # `EPIC-023B` — same construction recipe as
        # `TradingView._build_equity_chart`: a dedicated `ChartCard`
        # (account-level, not per-symbol — must not react to Dev Board's
        # own per-chart-card symbol list), line type, no volume/toolbar.
        self.equity_chart = ChartCard(_EQUITY_CHART_TITLE)
        self.equity_chart.setObjectName("equityChart")
        self.equity_chart.set_chart_type("line")
        self.equity_chart.set_volume_visible(False)
        self.equity_chart.toolbar.setVisible(False)
        self.equity_chart.setMinimumHeight(_EQUITY_CHART_MINIMUM_HEIGHT)
        self._surface.place_widget(Place.RAIL, self.equity_chart, title=EQUITY_DOCK)

    def set_view_model(self, view_model, context_name: str = "viewModel") -> None:
        """Builds the right-hand `DevBoardPanel` against `view_model` and
        places what it owns into the workbench: its three buttons in the
        header toolbar, the price ticker and websocket pill in the status bar
        (HLD §11.2 puts both there), the card column in a dock, and its log in
        the bottom dock.

        Called once per View. `PageShell`'s setters replaced a band's content
        on every call; a workbench part is *placed*, not re-set — a second
        `WORKSPACE`, or a second dock with a title already taken, is refused,
        which is the check that a screen is not quietly building two of
        something.
        """
        self._view_model = view_model
        self._panel = DevBoardPanel(view_model)

        for action_widget in self._panel.header_actions:
            self._surface.place_widget(Place.HEADER, action_widget)
        for tile in self._panel.status_tiles:
            self._surface.place_widget(Place.STATUS_TILE, tile)
        for title, card in self._panel.dock_panels:
            self._surface.place_widget(Place.RAIL, card, title=title)
        self._surface.place_widget(
            Place.MODAL, self._panel.manual_order_card, title=MANUAL_ORDER_DIALOG
        )
        self._surface.place_widget(
            Place.CONSOLE, self._panel.console_widget, title=MONITOR_DOCK
        )
        self._add_manual_order_action()
        self._place_contributed_panels()

    def _place_contributed_panels(self) -> None:
        """Adds whatever a module contributed to this surface, after this
        screen's own widgets are in place.

        Last, and deliberately: the workspace has to exist before the docks so
        Qt sizes the dock areas around a real central widget, and a contributed
        panel must not be able to take the centre from the screen that owns it.

        Nothing contributed, or no container to build with, means nothing to
        place — which is the normal case for `dev_board` with `dev.mode` off,
        because the registry drops those contributions at `contribute()` time
        with a log line each.
        """
        if self._contributions is None or self._container is None:
            return
        fill_surface(self._surface, self._contributions, self._container)

    def _add_manual_order_action(self) -> None:
        """`F9` raises the order dialog, and the same `QAction` sits in the
        header toolbar.

        One `QAction` per user action — it carries the shortcut, the toolbar
        button and the enabled state in one object, which is the Consistency
        and Efficiency pair HLD §11.2 asks for. `F9` because that is the key
        MetaTrader has used for "new order" for twenty years, and the design
        this workbench follows is theirs (HLD §11.2's "apply before you
        invent").
        """
        self._manual_order_action = QAction(MANUAL_ORDER_DIALOG, self)
        self._manual_order_action.setObjectName("actManualOrder")
        self._manual_order_action.setShortcut(QKeySequence("F9"))
        self._manual_order_action.setToolTip(f"{MANUAL_ORDER_DIALOG} (F9)")
        self._manual_order_action.triggered.connect(self.open_manual_order_dialog)
        self.addAction(self._manual_order_action)
        self._surface.place_widget(
            Place.HEADER, _action_button(self._manual_order_action)
        )

    def open_manual_order_dialog(self) -> None:
        """Shows the order dialog, non-modally: a user placing an order by
        hand is watching the chart behind it, and a modal `exec()` would
        freeze the ticks they are deciding on."""
        self._surface.show_modal(MANUAL_ORDER_DIALOG).show()

    def set_positions(self, rows: list[PositionRow]) -> None:
        self._positions_panel.set_rows(rows)

    def set_open_orders(self, rows: list[OpenOrderRow]) -> None:
        self._open_orders_panel.set_rows(rows)

    def set_symbol_preferences(self, preferences) -> None:
        """EPIC-014: DashboardPresenter injects the container-registered
        favourites/recents store here — this view, like BackTestView, has no
        container access. Forwarded to the panel, which owns the picker; a
        no-op before `set_view_model()` has built one."""
        if self._panel is not None:
            self._panel.set_symbol_preferences(preferences)

    def set_timeframe_pin_preferences(
        self, preferences: TimeframePinPreferences
    ) -> None:
        """Follow-up to `EPIC-015` Phase 4: `DashboardPresenter` injects the
        container-registered, per-symbol pinned-timeframe store here. Unlike
        `set_symbol_preferences` above, this View owns `render_symbol_cards`
        itself (it builds `ChartCard`s directly, not through a panel), so
        the store is kept on `self` and handed to every card built from now
        on — including a card rebuilt for a symbol already seen, which is
        exactly how it recovers that symbol's previously pinned set across
        Dev Board's symbol-list rebuilds."""
        self._timeframe_pin_preferences = preferences

    def apply_ui_mode(self, mode, section_key: str = "main") -> None:
        """Receives FSM state changes from BasePresenter (duck-typed fallback
        branch — this view has no `control_card`) and forwards them to the
        ViewModel's `uiMode` property, which DevBoardPanel binds against."""
        if self._view_model is None:
            return
        mode_value = getattr(mode, "value", mode)
        self._view_model.set_ui_mode(str(mode_value))

    def render_symbol_cards(self, symbols: list[str]) -> list:
        """
        @brief Dynamically instantiates ChartCards for given symbols.
        @returns A list of the created ChartCards.
        """
        # Clear existing cards first
        for i in reversed(range(self.charts_layout.count())):
            item = self.charts_layout.itemAt(i)
            widget = item.widget()
            if widget:
                # 1. Clear dữ liệu đồ họa ngầm của pyqtgraph
                if hasattr(widget, "cleanup"):
                    widget.cleanup()

                # 2. Xóa widget khỏi layout
                self.charts_layout.removeItem(item)

                # 3. Ra lệnh hủy hoàn toàn trong bộ nhớ C++
                widget.deleteLater()

        self.chart_cards = []

        for symbol in symbols:
            card = ChartCard(
                symbol, timeframe_pin_preferences=self._timeframe_pin_preferences
            )
            self.chart_cards.append(card)
            # Stretch factor 1: cards share the full available height instead of
            # shrinking to their minimum size (there is no trailing spacer item).
            self.charts_layout.addWidget(card, 1)

        return self.chart_cards
