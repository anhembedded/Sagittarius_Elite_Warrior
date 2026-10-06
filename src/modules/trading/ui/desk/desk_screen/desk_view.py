"""One venue's page of the Trade mode (`EPIC-033I`; the desk of `EPIC-028K`/
`028L`), laid out as HLD §11.2.1 lists the mode.

- **Central:** the chart of the traded symbol.
- **Header toolbar:** the symbol, and the venue's status line in words (an
  error reads "Error: …", as the order entry's does).
- **Right:** Order entry above Account summary, both in view; the order
  entry scrolls, once, at its panel.
- **Bottom, tabbed:** Positions (Futures) or Assets (Spot), Open orders,
  Order history, Trade history and Equity, as HLD §11.2.1 lists them, what
  is held in front; and Strategy until arming moves to the Bots mode
  (`EPIC-033K` stage 3).

Each venue's page is a `WorkbenchSurface` of its own (`trade.<venue>`), so
each keeps its own layout (HLD §11.2.1, `ISurfaceStack`). Stock controls,
no style sheet (`ui-presentation-rule.md` §1). Enable live trading,
Emergency stop and New order… are the mode's commands (`trade_commands.py`),
actions in the Trade menu and on its toolbar, not buttons here.

Built as an empty shell, without reading a service: the presenter side
decides what fills it. `attach` lays the page out once the presenter has its
view models (`OrderEntryPanel` and the strategy card each take theirs at
construction).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.core.contracts.place import Place
from Sagittarius_Elite_Warrior.src.core.contracts.surface import Surface
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_summary.account_summary_panel import (
    AccountSummaryPanel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_tabs.account_tab_confirmations import (
    AccountTabConfirmations,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_tabs.account_tabs_panel import (
    AccountTabsPanel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_profile import (
    DeskProfile,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_view_model import (
    DeskViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_panel import (
    OrderEntryPanel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_view_model import (
    OrderEntryViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.strategy_card.strategy_card import (
    StrategyCard,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.strategy_card.strategy_card_binding import (
    StrategyCardBinding,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card import ChartCard
from Sagittarius_Elite_Warrior.src.support.ui_kit.app_defaults import FALLBACK_SYMBOL
from Sagittarius_Elite_Warrior.src.support.ui_kit.minimum_hint_slot import (
    MinimumHintSlot,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.workbench_surface import (
    WorkbenchSurface,
)
from sagittarius_engine.extensions.pyside_mvc import LogListModel

#: The places of the Trade mode's surfaces. Declared here because a module
#: may not import `shell/`; `test_trade_view.py` holds it equal to
#: `shell/surfaces.py`'s `trade` entry.
TRADE_SURFACE = Surface(
    "trade",
    owner="trading",
    accepts=frozenset({Place.WORKSPACE, Place.HEADER, Place.RAIL, Place.CONSOLE}),
)
#: The panels' titles, which are also their View toggles' texts.
ORDER_ENTRY_TITLE = "Order entry"
ACCOUNT_SUMMARY_TITLE = "Account summary"
STRATEGY_TITLE = "Strategy"
#: The equity chart's title: the curve is the venue's account, not a symbol.
EQUITY_CHART_TITLE = "Equity"


def venue_surface(profile: DeskProfile) -> Surface:
    """The surface of `profile`'s venue: the Trade mode's places under the
    venue's own id, so its layout is saved apart from the other venue's."""
    return Surface(
        f"{TRADE_SURFACE.surface_id}.{profile.venue.value}",
        owner=TRADE_SURFACE.owner,
        accepts=TRADE_SURFACE.accepts,
    )


class DeskView(QWidget):  # base-exempt: a page of the Trade mode's view
    """@brief One venue's page of the Trade mode."""

    def __init__(
        self,
        profile: DeskProfile,
        *,
        log: LogListModel | None = None,
        confirmations: AccountTabConfirmations | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """@param log The log this venue's lines go to: the Trade mode's one
        Output channel; `None` keeps one of the page's own.
        @param confirmations How the tabs ask before a cancel or a close;
        `None` asks with the real dialogs."""
        super().__init__(parent)
        self.setObjectName(f"desk_{profile.venue.value}")
        self._profile = profile
        self.log_model = log if log is not None else LogListModel(self)
        self.chart = ChartCard(FALLBACK_SYMBOL)
        self.equity_chart = _equity_chart()
        self.account_tabs = AccountTabsPanel(
            profile.held_tab, confirmations, parent=self
        )
        # It owns the tables and draws none of them: each is a panel.
        self.account_tabs.hide()
        self.account_summary = AccountSummaryPanel()
        self._symbol = QComboBox()
        self._symbol.setObjectName("cboDeskSymbol")
        self._status = QLabel()
        self._status.setObjectName("lblDeskStatus")
        self._status.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.surface = WorkbenchSurface(venue_surface(profile))
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.surface)

    @property
    def profile(self) -> DeskProfile:
        return self._profile

    @property
    def status_text(self) -> str:
        return self._status.text()

    def attach(self, desk: DeskViewModel, order: OrderEntryViewModel) -> None:
        """Lays the page out: places the chart and the panels, built with
        their view models, and binds the context bar to `desk`."""
        panel = OrderEntryPanel(order)
        panel.setObjectName("orderEntryPanel")
        card = StrategyCard(
            StrategyCardBinding(
                strategy=desk.strategy_card,
                is_trading_enabled=lambda: bool(desk.enabled),
                trading_state_changed=desk.tradingStateChanged,
            ),
            market_type=self._profile.market_type,
        )
        card.setObjectName("deskStrategyCard")
        self._lay_out(panel, card)
        self._apply_symbols(desk)
        self._apply_status(desk)
        self._symbol.currentTextChanged.connect(desk.requestSymbolChange)
        desk.symbolOptionsChanged.connect(lambda: self._apply_symbols(desk))
        desk.symbolChanged.connect(lambda: self._apply_symbols(desk))
        desk.statusChanged.connect(lambda: self._apply_status(desk))

    def _lay_out(self, order_entry: QWidget, strategy: QWidget) -> None:
        surface = self.surface
        surface.place_widget(Place.WORKSPACE, self.chart)
        surface.place_widget(Place.HEADER, self._context_bar())
        self._place_right(_scrolling(order_entry, "scrollOrderEntry"))
        bottom: list[tuple[str, QWidget]] = [
            (title, MinimumHintSlot(table))
            for title, table in self.account_tabs.panels()
        ]
        bottom.append((EQUITY_CHART_TITLE, MinimumHintSlot(self.equity_chart)))
        bottom.append((STRATEGY_TITLE, _scrolling(strategy, "scrollStrategy")))
        for title, widget in bottom:
            surface.place_widget(Place.CONSOLE, widget, title=title)
        # What the account holds is what an order changes: in front.
        surface.dock_of(bottom[0][1]).raise_()

    def _place_right(self, entry: QWidget) -> None:
        """Order entry above Account summary, both in view, never tabbed.

        The surface tabs a second panel of one side with the first. Tabbed
        panels on two sides, made before the window first shows, leave a
        second, stale tab bar drawn over the panels (Qt 6, measured
        2026-10-06; Backtest and Bots tab one side only). So Order entry
        steps out of the right side while the summary is placed, and comes
        back above it: the bottom is this page's one tabbed side.
        """
        surface = self.surface
        surface.place_widget(Place.RAIL, entry, title=ORDER_ENTRY_TITLE)
        entry_dock = surface.dock_of(entry)
        surface.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, entry_dock)
        # The summary asks for its few lines only; the entry takes the rest.
        summary = MinimumHintSlot(self.account_summary)
        surface.place_widget(Place.RAIL, summary, title=ACCOUNT_SUMMARY_TITLE)
        summary_dock = surface.dock_of(summary)
        surface.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, entry_dock)
        surface.splitDockWidget(entry_dock, summary_dock, Qt.Orientation.Vertical)

    def _context_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("deskContextBar")
        row = QHBoxLayout(bar)
        row.setContentsMargins(0, 0, 0, 0)
        symbol = QLabel("&Symbol:")
        symbol.setBuddy(self._symbol)
        row.addWidget(symbol)
        row.addWidget(self._symbol)
        row.addWidget(self._status, 1)
        return bar

    def _apply_symbols(self, desk: DeskViewModel) -> None:
        self._symbol.blockSignals(True)
        options = desk.symbol_list
        if [self._symbol.itemText(i) for i in range(self._symbol.count())] != options:
            self._symbol.clear()
            self._symbol.addItems(options)
        if desk.current_symbol:
            self._symbol.setCurrentText(desk.current_symbol)
        self._symbol.blockSignals(False)

    def _apply_status(self, desk: DeskViewModel) -> None:
        text = str(desk.statusMessage)
        prefix = "Error: " if desk.statusIsError and text else ""
        self._status.setText(prefix + text)


def _scrolling(content: QWidget, name: str) -> QScrollArea:
    """`content` in a panel that scrolls once, at the panel, when the panel
    is shorter than it (`ui-presentation-rule.md` §3): the order entry and
    the strategy card are taller than a 1024×700 window leaves them."""
    scroll = QScrollArea()
    scroll.setObjectName(name)
    scroll.setWidgetResizable(True)
    scroll.setWidget(content)
    return scroll


def _equity_chart() -> ChartCard:
    """A plain `ChartCard` drawn as a line (`EPIC-021M` §3): equity has no
    OHLC, volume or timeframe of its own, so those are hidden, not removed."""
    card = ChartCard(EQUITY_CHART_TITLE)
    card.setObjectName("deskEquityChart")
    card.set_chart_type("line")
    card.set_volume_visible(False)
    card.toolbar.setVisible(False)
    return card
