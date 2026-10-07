"""`EPIC-028K`/`028L` — one desk's presenter: a composition of the desk kit
for one venue, one page of the Trade mode since `EPIC-033I`.

@details Every part already exists and is tested on its own: the order panel
(`EPIC-028H`/`028I`), the account tabs and summary (`EPIC-028J`), the TP/SL
follower (`EPIC-028I`), the chart. This
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
- each of the venue's fills is marked on the chart, and its equity curve is
  drawn below (both moved here from the single Trading screen, `EPIC-028M`);
- an entry placed with TP/SL is handed to the follower (Futures only: the
  Spot desk's TP/SL waits on `EPIC-026K`, ADR O2);
- the chart draws the strategy the venue has armed, re-read whenever an
  `ArmedStrategyChangedEvent` names the venue: the Bots mode arms it since
  `EPIC-033K` stage 3, and the desk keeps no strategy state of its own.

The Trade mode's commands (New order…, Emergency stop)
are bound by the mode (`trade_command_binding.py`) to the desk of the venue
chosen; this presenter offers what they act on (`desk`, `orders`).

Nothing here is shared with the other desk: each desk's ports, feeds, chart
stream and strategy are its own venue's, so an order, an armed strategy or a
candle on one never reaches the other (`EPIC-028L`).
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from PySide6.QtCore import Signal
from PySide6.QtGui import QAction
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.armed_strategy_changed_event import (
    ArmedStrategyChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.trading_switch_changed_event import (
    TradingSwitchChangedEvent,
)
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
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_equity import (
    DeskEquity,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_session_controls import (
    DeskSessionControls,
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
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.venue_key import (
    no_key_text,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.app_defaults import (
    FALLBACK_SYMBOL,
    FALLBACK_SYMBOL_OPTIONS,
    default_symbol,
    default_symbol_options,
)
from sagittarius_engine.extensions.pyside_mvc import BasePresenter

if TYPE_CHECKING:
    from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
        TradingVenue,
    )
    from sagittarius_engine.interfaces.i_container import IContainer

    from .desk_view import DeskView


class DeskPresenter(BasePresenter):
    """@brief Presenter for one desk (`EPIC-028K`/`028L`)."""

    #: What the Trade mode's commands show for this desk changed: trading
    #: on or off, a toggle in flight, the order entry able to take an order.
    commandStateChanged = Signal()

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
        if deps.strategy.venue is not profile.venue:
            raise ValueError(
                f"the {profile.title} desk was given {deps.strategy.venue.value}'s "
                "strategy"
            )
        self._profile = profile
        config = self.config.get_all()
        self.desk = DeskViewModel(
            self, log_model=view.log_model, log_prefix=f"{profile.title}: "
        )
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
        self._has_key = deps.has_key
        self.tabs = AccountTabsPresenter(
            view.account_tabs, ports, feeds.orders, threads, has_key=deps.has_key
        )
        view.account_tabs.use_precisions(deps.precisions)
        self.summary = AccountSummaryPresenter(
            view.account_summary, ports.account_activity, feeds.orders, threads
        )
        self.chart = DeskChart(view.chart, deps.chart, self.event_bus, self)
        feeds.orders.orderFilled.connect(self.chart.record_fill)
        # A fill moves what is available and what can be sold (`EPIC-028S`).
        feeds.orders.orderFilled.connect(self.order_entry.refresh)
        self.equity = DeskEquity(
            view.equity_chart, ports.equity_curve, feeds.equity, self
        )
        self.session = DeskSessionControls(
            ports.trading_session, threads, profile.venue, self
        )
        # The chart draws what its venue has armed; the Bots mode arms it
        # (`EPIC-033K` stage 3), and says so on the bus.
        self._armed = deps.strategy.armed
        self.subscribe(ArmedStrategyChangedEvent, self._on_armed_changed)
        # The chart goes live when this venue's order session opens, whichever
        # action opened it (`BUG-107`, `EPIC-034C`).
        self.subscribe(TradingSwitchChangedEvent, self._on_session_changed)
        self.follower: ProtectiveOrderFollower | None = None
        if profile.futures_controls:
            self.follower = ProtectiveOrderFollower(
                ports.order_submission, feeds.orders, threads, self.desk.set_status
            )
            follower = self.follower
            self.order_entry.entryPlaced.connect(
                lambda placed: follower.expect(*placed)
            )
        self._wire()
        if self.session.is_open:
            # The session opened before this desk did (another visit, a bot
            # started from the Bots mode): its chart is live, as when it
            # opens later, so the order panel values orders at the live price
            # (the PR 308 review).
            self.chart.go_live()
        self._draw_armed()
        if self._has_key():
            self.summary.refresh()
        else:
            # `EPIC-034B` — a venue with no key is a state, not a failure.
            view.account_summary.mark_stale(no_key_text(profile.venue))
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

    def _wire(self) -> None:
        desk, session, chart = self.desk, self.session, self.chart
        desk.symbolChangeRequested.connect(self.show_symbol)
        # A cancel's or a close's outcome is said on the page's status line:
        # the tables are panels of their own (`EPIC-033I` stage 2).
        self.view.account_tabs.messageShown.connect(
            lambda text: desk.set_status(text, False)
        )
        self.orders.changed.connect(self.commandStateChanged)
        self.order_entry.orderAccepted.connect(self.tabs.list_accepted_order)
        desk.emergencyStopRequested.connect(session.emergency_stop)
        session.statusChanged.connect(desk.set_status)
        session.logged.connect(self._log)
        session.accountChanged.connect(self._reread_account)
        chart.logged.connect(self._log)
        chart.lastPriceChanged.connect(self._on_last_price)

    def _on_last_price(self, price: Decimal) -> None:
        self.order_entry.update_last_price(price)
        self.tabs.update_last_price(price)

    def _reread_account(self) -> None:
        self.tabs.refresh()
        if self._has_key():
            self.summary.refresh()
        self.order_entry.refresh()

    @property
    def venue(self) -> TradingVenue:
        return self._profile.venue

    # -- what the Trade mode's commands act on (`trade_command_binding.py`) --

    @property
    def can_take_order(self) -> bool:
        return self.orders.can_take_order

    def request_emergency_stop(self) -> None:
        """Emergency stop, already confirmed: stops this venue — unless it has
        no key and no open session (`EPIC-034B`): it holds nothing the app can
        cancel or close, and a stop that could only fail would read as a
        partly failed one."""
        if not self._has_key() and not self.session.is_open:
            self.desk.set_status(
                f"{no_key_text(self._profile.venue)} Nothing to stop.", False
            )
            return
        self.desk.requestEmergencyStop()

    def request_new_order(self) -> None:
        """New order…: the keyboard focus to the order entry's first field."""
        self.orders.intents.request_focus()

    @property
    def title(self) -> str:
        """The venue's title, as the Trade menu names it."""
        return self._profile.title

    def table_actions(self) -> dict[str, QAction]:
        """The account tables' actions the Trade menu drives."""
        return self.view.account_tabs.menu_actions()

    @property
    def hides_other_pairs(self) -> bool:
        return self.view.account_tabs.hides_other_pairs

    def set_hide_other_pairs(self, hide: bool) -> None:
        """View → Hide other pairs: the account tables show this desk's
        symbol only."""
        self.view.account_tabs.set_hide_other_pairs(hide)

    def _on_session_changed(self, event: TradingSwitchChangedEvent) -> None:
        if event.venue is self._profile.venue and event.enabled:
            self.chart.go_live()

    def _on_armed_changed(self, event: ArmedStrategyChangedEvent) -> None:
        if event.venue is self._profile.venue:
            self._draw_armed()

    def _draw_armed(self) -> None:
        """The chart's strategy lines follow what the session has armed."""
        self.chart.set_armed_config(self._armed.armed().config)

    def _log(self, line: str) -> None:
        self.desk.write_log(line)
