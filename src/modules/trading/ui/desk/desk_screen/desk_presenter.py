"""`EPIC-028K`/`028L` — one desk's presenter: a composition of the desk kit
for one venue.

@details Every part already exists and is tested on its own: the order panel
(`EPIC-028H`/`028I`), the account tabs and summary (`EPIC-028J`), the TP/SL
follower (`EPIC-028I`), the strategy card (`EPIC-022D`), the chart. This
presenter builds each with the desk's own venue's ports and feeds, and wires
what passes between them:

- the symbol picked in the context bar reaches the chart, the order panel
  and the tabs;
- the chart's last price values the order panel's figures and the tabs'
  holdings;
- trading enabled on this desk puts its chart live, and so does opening the
  desk while its venue's trading is already on; opening a desk with trading
  off never touches the network (`BUG-107`);
- an Emergency Stop, or an enable that reconciled, re-reads the tables;
- an order the venue accepted joins Open orders at once;
- an entry placed with TP/SL is handed to the follower (Futures only: the
  Spot desk's TP/SL waits on `EPIC-026K`, ADR O2).

Nothing here is shared with the other desk: each desk's ports, feeds, chart
stream and strategy are its own venue's, so an order, a signal or a candle
on one never reaches the other (`EPIC-028L`).
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.modules.trading.ui import screen_venue_feeds
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_summary.account_summary_presenter import (
    AccountSummaryPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_tabs.account_tabs_presenter import (
    AccountTabsPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_profile import (
    DeskProfile,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_chart import (
    DeskChart,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_dependencies import (
    DeskDependencies,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_session_controls import (
    DeskSessionControls,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_strategy import (
    DeskStrategy,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_view_model import (
    DeskViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_panel import (
    confirm_with_message_box,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_presenter import (
    OrderEntryPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_view_model import (
    OrderEntryViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.protective_order_follower import (
    ProtectiveOrderFollower,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.signal_feed import SignalFeed
from Sagittarius_Elite_Warrior.src.support.ui_kit.app_defaults import (
    FALLBACK_SYMBOL,
    FALLBACK_SYMBOL_OPTIONS,
    default_symbol,
    default_symbol_options,
)
from sagittarius_engine.extensions.pyside_mvc import BasePresenter

if TYPE_CHECKING:
    from sagittarius_engine.interfaces.i_container import IContainer

    from .desk_view import DeskView


class DeskPresenter(BasePresenter):
    """@brief Presenter for one desk (`EPIC-028K`/`028L`)."""

    def __init__(
        self,
        view: DeskView,
        container: IContainer,
        profile: DeskProfile,
        deps: DeskDependencies,
    ) -> None:
        super().__init__(view, container)
        if deps.ports.venue is not profile.venue:
            raise ValueError(
                f"the {profile.title} desk was given {deps.ports.venue.value}'s ports"
            )
        self._profile = profile
        config = self.config.get_all()
        self.desk = DeskViewModel(self)
        self.desk.set_symbol_options(
            default_symbol_options(config, FALLBACK_SYMBOL_OPTIONS)
        )
        self.orders = OrderEntryViewModel(profile, self)
        view.attach(self.desk, self.orders)
        threads = deps.thread_manager
        ports = deps.ports
        feeds = screen_venue_feeds.build_for(self.event_bus, profile.venue, self)

        self.order_entry = OrderEntryPresenter(
            self.orders, ports, threads, deps.confirm or confirm_with_message_box(view)
        )
        self.tabs = AccountTabsPresenter(
            view.account_tabs, ports, feeds.orders, threads
        )
        self.summary = AccountSummaryPresenter(
            view.account_summary, ports.account_activity, feeds.orders, threads
        )
        self.chart = DeskChart(view.chart, deps.chart, self.event_bus, self)
        self.session = DeskSessionControls(
            ports.trading_session, threads, profile.venue, self
        )
        self.strategy = DeskStrategy(self.desk, deps.strategy, deps.catalog, self.chart)
        self.follower: ProtectiveOrderFollower | None = None
        if profile.futures_controls:
            self.follower = ProtectiveOrderFollower(
                ports.order_submission, feeds.orders, threads, self.desk.set_status
            )
            follower = self.follower
            self.order_entry.entryPlaced.connect(
                lambda placed: follower.expect(*placed)
            )
        self._wire(feeds.signals)
        self.desk.set_trading_state(self.session.is_enabled, False)
        if self.session.is_enabled:
            # Trading was turned on before this desk opened (another visit, or
            # the old screen): its chart is live, as after the toggle, so the
            # order panel values orders at the live price (the PR 308 review).
            self.chart.go_live()
        self.strategy.refresh()
        self.summary.refresh()
        self.show_symbol(default_symbol(config, FALLBACK_SYMBOL))

    def show_symbol(self, symbol: str) -> None:
        """Points the chart, the order panel and the tabs at `symbol`."""
        symbol = symbol.strip().upper()
        if not symbol or symbol == self.chart.shown_symbol:
            return
        self.desk.set_symbol(symbol)
        self.chart.show_symbol(symbol)
        self.order_entry.show_symbol(symbol)
        self.tabs.show_symbol(symbol)

    def shutdown(self) -> None:
        self.chart.shutdown()
        super().shutdown()

    def _wire(self, signals: SignalFeed) -> None:
        desk, session, chart = self.desk, self.session, self.chart
        desk.symbolChangeRequested.connect(self.show_symbol)
        self.order_entry.orderAccepted.connect(self.tabs.list_accepted_order)
        desk.toggleRequested.connect(session.toggle)
        desk.emergencyStopRequested.connect(session.emergency_stop)
        session.stateChanged.connect(desk.set_trading_state)
        session.statusChanged.connect(desk.set_status)
        session.logged.connect(self._log)
        session.tradingEnabled.connect(chart.go_live)
        session.accountChanged.connect(self._reread_account)
        chart.logged.connect(self._log)
        chart.lastPriceChanged.connect(self._on_last_price)
        self.strategy.listen(signals)

    def _on_last_price(self, price: Decimal) -> None:
        self.order_entry.update_last_price(price)
        self.tabs.update_last_price(price)

    def _reread_account(self) -> None:
        self.tabs.refresh()
        self.summary.refresh()
        self.order_entry.refresh()

    def _log(self, line: str) -> None:
        self.desk.log_model.append(line, level="info")
