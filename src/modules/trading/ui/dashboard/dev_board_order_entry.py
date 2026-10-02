"""`EPIC-028M` — the Dev Board's order dialog (F9): the desks' own order
panel, for the venue this board trades.

@details The Dev Board had its own manual-order card (`EPIC-024B`): Long or
Short, Market or Limit, one quantity. The desks have the full order panel
(`EPIC-028H`/`028I`): every order type the venue takes, its estimates, its
balances, TP/SL on Futures. Two forms placing orders on one venue would drift
apart, so the dialog now hosts the panel and the card is gone.

The venue is the one this board trades (`TradingVenue`, the primary enabled
venue), shown with its desk's profile. With no venue enabled the dialog says
so and holds nothing that sends an order, as a disabled desk does.

What the board passes the panel, and what it takes back:
- the board's symbol, and its last price while the board charts that venue's
  market (a Spot chart's price is not a Futures order's price);
- each order the venue accepted, for the board's Open orders: the venue's
  stream announces an order only when it fills or ends (`EPIC-028K`);
- on Futures, each entry placed with TP/SL, for the follower that places them
  once it fills (`EPIC-028I`), as a desk does.

Extension cases, each local: a venue picker in the dialog (one argument
here); a second board (one more instance).
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from PySide6.QtCore import QObject, Signal
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_trading_ports import (
    VenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_profile import (
    desk_profile_for,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_confirmation import (
    ConfirmOrder,
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
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_feed import OrderFeed
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager


class DevBoardOrderEntry(QObject):
    """@brief The order panel behind the Dev Board's F9, for one venue."""

    #: An order the venue accepted (an `Order`), for the board's Open orders.
    orderAccepted = Signal(object)

    def __init__(
        self,
        ports: VenueTradingPorts,
        thread_manager: IThreadManager,
        confirm: ConfirmOrder,
        feed: OrderFeed,
        report: Callable[[str], None],
        parent: QObject | None = None,
    ) -> None:
        """@param feed The venue's order feed: the TP/SL follower waits on it.
        @param report Where the follower's outcome lines go (the board's log).
        """
        super().__init__(parent)
        profile = desk_profile_for(ports.venue)
        self._market = ports.venue.market_type
        self.view_model = OrderEntryViewModel(profile, self)
        self._presenter = OrderEntryPresenter(
            self.view_model, ports, thread_manager, confirm
        )
        self._presenter.orderAccepted.connect(self.orderAccepted)
        self._follower: ProtectiveOrderFollower | None = None
        if profile.futures_controls:
            follower = ProtectiveOrderFollower(
                ports.order_submission,
                feed,
                thread_manager,
                lambda text, _is_error: report(text),
            )
            self._follower = follower
            self._presenter.entryPlaced.connect(lambda placed: follower.expect(*placed))

    def show_symbol(self, symbol: str) -> None:
        """Points the panel at the board's symbol."""
        if symbol and symbol != self.view_model.order_symbol:
            self._presenter.show_symbol(symbol)

    def update_last_price(self, market: MarketType, price: Decimal) -> None:
        """The board's last price, taken only from this venue's market."""
        if market is self._market:
            self._presenter.update_last_price(price)

    def refresh(self) -> None:
        """Re-reads the panel's balances, after a fill for instance."""
        self._presenter.refresh()
