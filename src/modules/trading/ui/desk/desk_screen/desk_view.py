"""`EPIC-028K`/`028L` — one desk's screen: the chart, the venue's equity
curve and the account tabs below it, and a rail holding the order panel, the strategy card and the account
summary; Enable/Disable and Emergency Stop for this venue only.

@details A `PageShell`, like the single Trading screen it replaced in
`EPIC-028M` (the workbench conversion of every remaining `PageShell` is
`EPIC-025`'s). Plain QtWidgets in the OS theme (ADR
D20–D22): no stylesheet, no colour; an error in the status line reads
"Error: …", as the order panel's does.

Built as an empty shell, like every screen's view, without reading a
service: the presenter side decides what fills it. `attach` lays the desk
out once the presenter has its view models (`OrderEntryPanel` and the
strategy card each take theirs at construction); `show_venue_disabled`
lays out the notice instead.

**A venue that is not enabled** shows one line naming the venue and where to
turn it on, and nothing that could send an order: no toggle, no Emergency
Stop, no rail.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.dashboard.dev_board_widgets.strategy_card import (
    StrategyCard,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.dashboard.dev_board_widgets.strategy_card_binding import (
    StrategyCardBinding,
)
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
from Sagittarius_Elite_Warrior.src.support.charting.chart_card import ChartCard
from Sagittarius_Elite_Warrior.src.support.ui_kit.app_defaults import FALLBACK_SYMBOL
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import PageShell
from Sagittarius_Elite_Warrior.src.support.ui_kit.output_source_view import (
    OutputSourceView,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.output_pane import OutputChannel

#: The equity chart's title: the curve is the venue's account, not a symbol.
EQUITY_CHART_TITLE = "Equity"
_TOGGLE_TEXT = {(False, False): "Enable Trading", (True, False): "Disable Trading"}
_BUSY_TEXT = "Processing..."


def disabled_text(profile: DeskProfile) -> str:
    """What a desk whose venue is not enabled says."""
    return (
        f"{profile.title} Testnet is not enabled — turn it on in "
        "Tools > Options > Trading, then restart the app."
    )


class DeskView(OutputSourceView):
    """@brief The View for one desk (`EPIC-028K`/`028L`)."""

    def __init__(
        self,
        profile: DeskProfile,
        *,
        confirmations: AccountTabConfirmations | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """@param confirmations How the tabs ask before a cancel or a close;
        `None` asks with the real dialogs."""
        super().__init__(parent)
        self.setObjectName(f"desk_{profile.venue.value}")
        self._profile = profile
        self.chart = ChartCard(FALLBACK_SYMBOL)
        self.equity_chart = _equity_chart()
        self.account_tabs = AccountTabsPanel(profile.held_tab, confirmations)
        self.account_summary = AccountSummaryPanel()
        self._toggle = QPushButton(_TOGGLE_TEXT[(False, False)])
        self._toggle.setObjectName("btnToggleTrading")
        self._emergency_stop = QPushButton("EMERGENCY STOP")
        self._emergency_stop.setObjectName("btnEmergencyStop")
        self._symbol = QComboBox()
        self._symbol.setObjectName("cboDeskSymbol")
        self._status = QLabel()
        self._status.setObjectName("lblDeskStatus")
        self._status.setWordWrap(True)
        self._rail = QVBoxLayout()
        self._shell = PageShell()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._shell)
        self._shell.set_header(f"{profile.title} · Testnet")

    @property
    def emergency_stop_button(self) -> QPushButton:
        return self._emergency_stop

    @property
    def toggle_button(self) -> QPushButton:
        return self._toggle

    @property
    def status_text(self) -> str:
        return self._status.text()

    def attach(self, desk: DeskViewModel, order: OrderEntryViewModel) -> None:
        """Lays the desk out: builds the rail's bound widgets and binds the
        header and the context bar to `desk`."""
        self._build_desk()
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
        self._rail.insertWidget(0, panel)
        self._rail.insertWidget(1, card)
        self._output = OutputChannel(
            f"desk.{self._profile.venue.value}", self._profile.title, desk.log_model
        )
        self._apply_symbols(desk)
        self._apply_state(desk)
        self._apply_status(desk)
        self._symbol.currentTextChanged.connect(desk.requestSymbolChange)
        self._toggle.clicked.connect(desk.requestToggle)
        self._emergency_stop.clicked.connect(desk.requestEmergencyStop)
        desk.symbolOptionsChanged.connect(lambda: self._apply_symbols(desk))
        desk.symbolChanged.connect(lambda: self._apply_symbols(desk))
        desk.tradingStateChanged.connect(lambda: self._apply_state(desk))
        desk.statusChanged.connect(lambda: self._apply_status(desk))

    def _apply_symbols(self, desk: DeskViewModel) -> None:
        self._symbol.blockSignals(True)
        options = desk.symbol_list
        if [self._symbol.itemText(i) for i in range(self._symbol.count())] != options:
            self._symbol.clear()
            self._symbol.addItems(options)
        if desk.current_symbol:
            self._symbol.setCurrentText(desk.current_symbol)
        self._symbol.blockSignals(False)

    def _apply_state(self, desk: DeskViewModel) -> None:
        busy = bool(desk.toggleBusy)
        self._toggle.setEnabled(not busy)
        self._toggle.setText(
            _BUSY_TEXT if busy else _TOGGLE_TEXT[(bool(desk.enabled), False)]
        )

    def _apply_status(self, desk: DeskViewModel) -> None:
        text = str(desk.statusMessage)
        prefix = "Error: " if desk.statusIsError and text else ""
        self._status.setText(prefix + text)

    def _build_desk(self) -> None:
        self._shell.set_header(
            f"{self._profile.title} · Testnet",
            "Manual orders, a strategy and the account, for this venue only",
            actions=self._toggle,
        )
        self._shell.set_context_bar(self._context_bar())
        workspace = QSplitter(Qt.Orientation.Vertical)
        workspace.setObjectName("deskWorkspace")
        workspace.addWidget(self.chart)
        workspace.addWidget(self.equity_chart)
        workspace.addWidget(self.account_tabs)
        workspace.setStretchFactor(0, 3)
        workspace.setStretchFactor(1, 1)
        workspace.setStretchFactor(2, 2)
        rail = QWidget()
        rail.setLayout(self._rail)
        self._rail.setContentsMargins(0, 0, 0, 0)
        self._rail.addWidget(self.account_summary)
        self._rail.addStretch(1)
        self._shell.set_workspace(workspace, rail=rail)

    def _context_bar(self) -> QWidget:
        bar = QWidget()
        row = QHBoxLayout(bar)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(QLabel("Symbol:"))
        row.addWidget(self._symbol)
        row.addWidget(self._status, 1)
        row.addWidget(self._emergency_stop)
        return bar

    def show_venue_disabled(self) -> None:
        """Lays out the notice of a venue that is not enabled."""
        self._build_disabled()

    def _build_disabled(self) -> None:
        self._shell.set_header(f"{self._profile.title} · Testnet", "Not enabled")
        notice = QLabel(disabled_text(self._profile))
        notice.setObjectName("lblDeskDisabled")
        notice.setWordWrap(True)
        notice.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._shell.set_workspace(notice)


def _equity_chart() -> ChartCard:
    """A plain `ChartCard` drawn as a line (`EPIC-021M` §3): equity has no
    OHLC, volume or timeframe of its own, so those are hidden, not removed."""
    card = ChartCard(EQUITY_CHART_TITLE)
    card.setObjectName("deskEquityChart")
    card.set_chart_type("line")
    card.set_volume_visible(False)
    card.toolbar.setVisible(False)
    return card
