"""Standalone preview of the Trade mode (`ui-presentation-rule.md` §5),
without an exchange: both venues' pages, Futures shown, each laid out as a
user sees it before the first read lands; and, in a second tab, the mode
with no venue enabled."""

from __future__ import annotations

from PySide6.QtWidgets import QTabWidget, QWidget
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_profile import (
    desk_profile_for,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.preview import (
    fill_page,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.trade.trade_view import (
    TradeView,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


def build_preview() -> QWidget:
    view = TradeView()
    for venue in (TradingVenue.FUTURES_TESTNET, TradingVenue.SPOT_TESTNET):
        fill_page(view.add_venue(desk_profile_for(venue)))
    tabs = QTabWidget()
    tabs.addTab(view, "Two venues")
    tabs.addTab(TradeView(), "No venue enabled")
    tabs.setWindowTitle("Trade")
    return tabs
