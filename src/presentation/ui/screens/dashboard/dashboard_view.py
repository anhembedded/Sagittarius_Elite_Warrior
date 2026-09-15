from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.core.contracts.place import Place
from Sagittarius_Elite_Warrior.src.core.contracts.surface import Surface
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card import (
    ChartCard,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.timeframe_pin_preferences import (
    TimeframePinPreferences,
)
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
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import (
    PreferredHeightScrollArea,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.workbench_surface import (
    WorkbenchSurface,
)
from sagittarius_engine.extensions.pyside_mvc import BaseView

from .dev_board_panel import DevBoardPanel

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

#: Dock titles. A title is the user's handle on a panel — what the View menu
#: lists, what a floating panel's title bar reads, and what `saveState()` keys
#: a dock by, so renaming one drops that panel out of every saved perspective.
POSITIONS_DOCK = "Positions"
OPEN_ORDERS_DOCK = "Open orders"
EQUITY_DOCK = "Equity"
CONTROLS_DOCK = "Controls"
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


class DashboardView(BaseView):
    """
    @brief The View for the Dev Board Screen — a developer testbed, not the
    app's end-user dashboard.

    @details A **workbench** since `EPIC-025` PR 1.4c-2: one nested
    `QMainWindow` (`WorkbenchSurface`) whose central widget is the scrolling
    column of `ChartCard`s, with everything else in a `QDockWidget` the user
    can move, tab, float, hide and have remembered — Positions, Open orders,
    Equity and the Controls column on the right, the System Monitor log at the
    bottom, the price ticker and websocket pill in the status bar.

    Before it was a `PageShell` holding one `QSplitter`: two fixed panes,
    neither hideable, and a rail column too narrow for a many-column table
    (`BOT-128`) — which is why the two account tables used to sit squeezed
    above the charts instead of beside them.

    What did not change: `DevBoardPanel` is still one widget built lazily at
    `set_view_model()` time (it needs a real ViewModel to construct against),
    the chart column is still QtWidgets/pyqtgraph, and FSM state still reaches
    the panel through `apply_ui_mode` → the ViewModel's `uiMode` property.
    Splitting that thousand-line panel into one dock per card is 1.4c-3.
    """

    #: `EPIC-024B` §0 — re-exposes `OpenOrdersPanel.cancelRequested`, same
    #: layered re-export the panel itself does for its own table.
    cancelOrderRequested = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._view_model = None
        self._panel: DevBoardPanel | None = None
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
        self._surface.place_widget(Place.RAIL, self._panel, title=CONTROLS_DOCK)
        self._surface.place_widget(
            Place.CONSOLE, self._panel.console_widget, title=MONITOR_DOCK
        )

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
