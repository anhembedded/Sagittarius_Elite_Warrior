"""`EPIC-028J` — drives one desk's account tabs: loads them from the
venue when the desk opens, keeps them current from the venue's own events,
and runs the tabs' actions.

@details **Loaded from queries, then kept by events.** A desk opened after
an order was placed elsewhere (the other desk, Binance's own UI) must still
list it, so opening reads the account (`IAccountActivity.open_orders`,
`IAccountSnapshot`) and hands the snapshot to `LiveOrderBookCoordinator`'s
full reconciliation. From then on the `OrderFeed` of the desk's venue keeps
the live tables current, as on the older screens: a fill adds or updates a
row, an order that ended anywhere without filling leaves Open orders
(`OrderEndedEvent`); a Spot fill never reaches
a Futures desk because the feed filters by venue (`EPIC-028C`).

**Histories** are `HistoryTabsLoader`'s; "hide other pairs" reopens them
for the desk's symbol or every active pair. **Actions** are
`AccountTabActions`'; a confirmed cancel removes the row, a close re-reads
the tables.

Every port is the desk's own venue's (`VenueTradingPorts`).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal

from PySide6.QtCore import QObject, Signal
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_ended_event import (
    OrderEndedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_filled_event import (
    OrderFilledEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.spot_holding import (
    SpotHolding,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_trading_ports import (
    VenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_tabs.account_tab_actions import (
    AccountTabActions,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_tabs.account_tabs_panel import (
    AccountTabsPanel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_tabs.history_tabs_loader import (
    Clock,
    HistoryTabsLoader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_tabs.history_view import (
    HistoryKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.live_order_book_coordinator import (
    LiveOrderBookCoordinator,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.holding_prices import (
    holding_price_for_symbol,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_feed import OrderFeed
from Sagittarius_Elite_Warrior.src.support.ui_kit.action_ownership_tracker import (
    ActionOutcome,
    ActionOwnershipTracker,
)
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

logger = logging.getLogger("App.Trading.AccountTabs")

_LOAD = "load"


def _utc_now() -> datetime:
    return datetime.now(UTC)


class AccountTabsPresenter(QObject):
    """@brief One desk's account tabs, loaded and kept current."""

    _loaded = Signal(object)

    def __init__(
        self,
        view: AccountTabsPanel,
        ports: VenueTradingPorts,
        feed: OrderFeed,
        thread_manager: IThreadManager,
        clock: Clock = _utc_now,
    ) -> None:
        super().__init__(view)
        self._view = view
        self._ports = ports
        self._threads = thread_manager
        self._symbol = ""
        self._last_price: Decimal | None = None
        self._holdings: tuple[SpotHolding, ...] = ()
        self._loads: ActionOwnershipTracker[str, str, None] = ActionOwnershipTracker()
        self._book = LiveOrderBookCoordinator(view, self._log_blocked)
        self._histories = HistoryTabsLoader(
            view, ports.account_activity, thread_manager, clock
        )
        self._actions = AccountTabActions(ports, thread_manager)

        self._loaded.connect(self._on_loaded)
        view.cancelRequested.connect(self._actions.cancel_one)
        view.cancelAllRequested.connect(self._actions.cancel_all)
        view.closePositionRequested.connect(self._actions.close_position)
        view.hideOtherPairsChanged.connect(self._reopen_histories)
        view.historyPageRequested.connect(self._on_page_requested)
        self._actions.orderCancelled.connect(self._book.on_order_cancelled)
        self._actions.finished.connect(lambda text, _failed: view.show_message(text))
        self._actions.positionCloseSent.connect(lambda _symbol: self.refresh())
        feed.orderFilled.connect(self._on_order_event)
        feed.orderEnded.connect(self._on_order_ended)
        feed.positionChanged.connect(
            lambda event: self._book.on_position_changed(event.position)
        )
        feed.positionClosed.connect(
            lambda event: self._book.on_position_closed(event.symbol)
        )
        feed.holdingsChanged.connect(
            lambda event: self._replace_holdings(event.holdings)
        )
        feed.orderBlocked.connect(
            lambda event: self._book.on_order_blocked(event.symbol, event.reason)
        )

    # -- the host ------------------------------------------------------ #

    def show_symbol(self, symbol: str) -> None:
        """Points the tabs at the desk's symbol and reads everything."""
        self._symbol = symbol
        self._view.set_desk_symbol(symbol)
        self.refresh()

    def refresh(self) -> None:
        """Reads the live tables and starts both histories over."""
        action = self._loads.begin_action(_LOAD, self._symbol, None)
        self._threads.submit(self._run_load, action.action_id)
        self._reopen_histories(self._view.hides_other_pairs)

    def list_accepted_order(self, order: Order) -> None:
        """`EPIC-028K` — an order this desk just placed joins Open orders as
        the venue accepted it. The venue's stream announces an order only
        when it fills or ends, so a resting Limit would otherwise stay off
        the table, uncancellable from the desk, until the next read. Both
        trading adapters answer an accepted order `NEW`, a filled Market
        order included, and the fill can reach this thread before or after
        that answer: the book applies a status only when it moves forward
        and never re-lists an order it saw end (`LiveOrderBookCoordinator.
        on_order_filled`, the PR 308 review)."""
        self._book.on_order_filled(order)

    def update_last_price(self, price: Decimal | None) -> None:
        """The desk symbol's last price, which values its base asset."""
        self._last_price = price
        self._replace_holdings(self._holdings)

    # -- load ---------------------------------------------------------- #

    def _run_load(self, action_id: int) -> None:
        try:
            orders = self._ports.account_activity.open_orders()
            account = self._ports.account_snapshot
            positions = account.open_positions()
            holdings: tuple[SpotHolding, ...] | None = None
            if self._ports.venue.market_type is MarketType.SPOT:
                holdings = account.check_connection().holdings or ()
            self._loaded.emit((action_id, (positions, orders, holdings), None))
        except Exception as exc:  # noqa: BLE001 - worker boundary: report the real failure instead of losing it to a background-thread traceback
            self._loaded.emit((action_id, None, str(exc)))

    def _on_loaded(self, payload: tuple) -> None:
        action_id, snapshot, error = payload
        if not self._loads.is_current_pending(action_id, _LOAD):
            self._loads.log_stale_callback("_on_loaded", action_id, _LOAD)
            return
        if snapshot is None:
            self._loads.finish_action(action_id, ActionOutcome.FAILED)
            logger.warning(
                "Account tabs could not read %s: %s", self._ports.venue.value, error
            )
            self._view.show_message(f"Could not read the account: {error}")
            return
        self._loads.finish_action(action_id, ActionOutcome.SUCCEEDED)
        positions, orders, holdings = snapshot
        logger.info(
            "Account tabs loaded %s: %d open orders, %d positions",
            self._ports.venue.value,
            len(orders),
            len(positions),
        )
        self._book.replace_all(positions, orders)
        if holdings is not None:
            self._replace_holdings(holdings)

    # -- events and the view ------------------------------------------- #

    def _on_order_event(self, event: OrderFilledEvent) -> None:
        self._book.on_order_filled(event.order)
        self._histories.reread()

    def _on_order_ended(self, event: OrderEndedEvent) -> None:
        """An order cancelled, rejected or expired anywhere (the other desk,
        Binance's site, a strategy, the exchange) leaves Open orders, and
        Order history is read again, and shows it at most
        `HISTORY_CACHE_TTL` late, as for a fill (the review of PR 307)."""
        self._book.on_order_cancelled(str(event.order.client_order_id))
        self._histories.reread()

    def _reopen_histories(self, hide_other_pairs: bool) -> None:
        symbol = self._symbol if hide_other_pairs and self._symbol else None
        self._histories.open(symbol, self._symbol)

    def _on_page_requested(self, kind_value: str, page: int) -> None:
        self._histories.turn_to(HistoryKind(kind_value), page)

    def _replace_holdings(self, holdings: tuple[SpotHolding, ...]) -> None:
        self._holdings = holdings
        prices = holding_price_for_symbol(self._symbol, self._last_price)
        self._book.replace_holdings(holdings, prices)

    def _log_blocked(self, text: str) -> None:
        self._view.show_message(text)
