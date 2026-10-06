"""Standalone preview of one venue's page of the Trade mode
(`ui-presentation-rule.md` §5), without an exchange.

The Futures page laid out as a user sees it before the first read lands: an
empty chart, empty tables, the order entry waiting on the pair's terms. The
panels' own previews show them filled (`order_entry/`, `account_tabs/`,
`account_summary/`); the mode with both venues is `trade/preview.py`."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_profile import (
    desk_profile_for,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_view import (
    DeskView,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_view_model import (
    DeskViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_view_model import (
    OrderEntryViewModel,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


def build_preview() -> QWidget:
    view = DeskView(desk_profile_for(TradingVenue.FUTURES_TESTNET))
    fill_page(view)
    view.setWindowTitle("Trade — one venue")
    return view


def fill_page(view: DeskView) -> None:
    """Attaches view models to `view` as its presenter would, unread."""
    view.chart.set_symbol_title("BTCUSDT")
    desk = DeskViewModel(view, log_model=view.log_model)
    desk.set_symbol_options(["BTCUSDT", "ETHUSDT"])
    desk.set_symbol("BTCUSDT")
    desk.set_status("Trading is off for this venue.", False)
    orders = OrderEntryViewModel(view.profile, view)
    orders.presenter_side().begin_symbol("BTCUSDT")
    view.attach(desk, orders)
