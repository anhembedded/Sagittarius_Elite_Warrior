"""Standalone preview of the two desks (`ui-presentation-rule.md` §5),
without an exchange.

A tab per desk: the Futures desk with its venue enabled, laid out as a user
sees it before the first read lands (an empty chart, empty tables, the order
panel waiting on the pair's terms), and the Spot desk as it opens when Spot
Testnet is not enabled — the one line saying so, and nothing that could send
an order. The panels' own previews show them filled (`order_entry/`,
`account_tabs/`, `account_summary/`)."""

from __future__ import annotations

from PySide6.QtWidgets import QTabWidget, QWidget
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_profile import (
    desk_profile_for,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_view import (
    DeskView,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_view_model import (
    OrderEntryViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.trading.trading_view_model import (
    TradingViewModel,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


def build_preview() -> QWidget:
    tabs = QTabWidget()
    tabs.addTab(_enabled_desk(TradingVenue.FUTURES_TESTNET), "Futures")
    disabled = DeskView(desk_profile_for(TradingVenue.SPOT_TESTNET))
    disabled.show_venue_disabled()
    tabs.addTab(disabled, "Spot (not enabled)")
    tabs.setWindowTitle("Desks")
    return tabs


def _enabled_desk(venue: TradingVenue) -> QWidget:
    profile = desk_profile_for(venue)
    view = DeskView(profile)
    view.chart.set_symbol_title("BTCUSDT")
    desk = TradingViewModel(view)
    desk.set_symbol_options(["BTCUSDT", "ETHUSDT"])
    desk.set_symbol("BTCUSDT")
    desk.set_status("Trading is off for this venue.", False)
    orders = OrderEntryViewModel(profile, view)
    orders.begin_symbol("BTCUSDT")
    view.attach(desk, orders)
    return view
