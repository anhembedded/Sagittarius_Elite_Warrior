from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
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
    PageShell,
    PreferredHeightScrollArea,
)
from sagittarius_engine.extensions.pyside_mvc import BaseView

from .dev_board_panel import DevBoardPanel

_TITLE = "Developer Board (Live Testbed)"
_SUBTITLE = "Test indicators & scripts on live data"

#: `EPIC-023B` — the equity chart's `ChartCard(symbol=...)` title, same
#: constant `TradingView` uses for its own equity chart.
_EQUITY_CHART_TITLE = "Equity"

#: An empty `ChartCard`'s own `sizeHint()` is tiny (no candles/toolbar to
#: size around) — `workspace_layout`'s stretch factors only split space
#: *beyond* each widget's own minimum, so a near-zero minimum here left
#: the equity chart squeezed to a sliver rather than sharing fairly in the
#: split, cramped axis labels and all (user-reported). This floor gives it
#: a legible baseline; `PageShell.set_workspace()` already wraps the whole
#: workspace in a `PreferredHeightScrollArea` (`kit/page_shell.py`), so if
#: this floor plus everything else no longer fits the viewport, the page
#: scrolls instead of compressing this chart back down.
_EQUITY_CHART_MINIMUM_HEIGHT = 220


class DashboardView(BaseView):
    """
    @brief The View for the Dev Board Screen — a developer testbed, not the
    app's end-user dashboard.

    @details
    Hybrid layout (BOT-030 Phase 4, migrated off QML at EPIC-006D): a
    QSplitter with the dynamic ChartCards (QtWidgets/pyqtgraph — stays that
    way permanently) on the left, and a `DevBoardPanel` (top bar, System
    Controls, Indicators, Monitor log) on the right. FSM state reaches the
    panel through `apply_ui_mode` -> the view model's `uiMode` property,
    same mechanism as before — only the render layer changed.

    `EPIC-023A` adds the account-wide Vị thế/Lệnh chờ khớp tables above the
    chart-card column, in the workspace rather than `DevBoardPanel`'s rail
    — a rail column is too narrow for a many-column table (`BOT-128`'s own
    finding, same tables `TradingView` places in its workspace for the
    same reason). `EPIC-023B` adds the same account-wide equity chart below
    the chart-card column, reusing `TradingView`'s own construction recipe.
    """

    #: `EPIC-024B` §0 — re-exposes `OpenOrdersPanel.cancelRequested`, same
    #: layered re-export the panel itself does for `OpenOrdersVM`'s signal.
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

        self._shell = PageShell()
        outer_layout.addWidget(self._shell)
        # No header actions/console yet — both live on `DevBoardPanel`,
        # which isn't built until `set_view_model()` (it needs the
        # ViewModel at construction). Re-set below once it exists.
        self._shell.set_header(_TITLE, _SUBTITLE)

        # `EPIC-023A` — positions and open orders, account-wide, the same
        # widgets `TradingView` embeds (they live in
        # `components/order_book/` for exactly this reuse — see that
        # package's docstring; QtWidgets since PR 1.4b-2).
        self._positions_panel = PositionsPanel()
        self._positions_panel.setObjectName("positionsPanel")
        self._open_orders_panel = OpenOrdersPanel()
        self._open_orders_panel.setObjectName("openOrdersPanel")
        self._open_orders_panel.cancelRequested.connect(self.cancelOrderRequested)

        tables_row = QWidget()
        tables_layout = QHBoxLayout(tables_row)
        tables_layout.setContentsMargins(0, 0, 0, 0)
        tables_layout.setSpacing(12)
        tables_layout.addWidget(self._positions_panel, 1)
        tables_layout.addWidget(self._open_orders_panel, 1)

        # Main workspace content: QScrollArea for dynamic ChartCards.
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

        self._workspace = QWidget()
        workspace_layout = QVBoxLayout(self._workspace)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(12)
        # Stretch, not just sizeHint — `Panel`/`QQuickWidget` reports a
        # near-zero natural sizeHint (`TradingView._build_workspace` gives
        # its own copy of these same two panels a stretch factor for the
        # exact same reason), so a bare `addWidget(tables_row)` with no
        # factor squeezed both tables down to an unreadable sliver, visible
        # only once actually screenshotted — offscreen `pytest` alone never
        # catches this class of layout defect. `equity_chart` gets the same
        # treatment up front this time, not as a second bug to find later.
        workspace_layout.addWidget(tables_row, 1)
        workspace_layout.addWidget(self.scroll_area, 3)
        workspace_layout.addWidget(self.equity_chart, 1)

        self._shell.set_workspace(self._workspace)

    def set_view_model(self, view_model, context_name: str = "viewModel") -> None:
        """Builds the right-hand DevBoardPanel against `view_model` — the
        panel takes its ViewModel at construction time (no late-binding
        needed, unlike the old QML context-property registration this
        replaces). Now the `PageShell` rail, not a second `QSplitter` pane
        this view built by hand — its header widgets and console log move
        into the shell's own header/console bands."""
        self._view_model = view_model
        self._panel = DevBoardPanel(view_model)
        self._shell.set_header(_TITLE, _SUBTITLE, actions=self._panel.header_actions)
        self._shell.set_workspace(self._workspace, rail=self._panel)
        self._shell.set_console(self._panel.console_widget)

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
