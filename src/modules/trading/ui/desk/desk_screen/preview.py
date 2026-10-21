"""Standalone preview of one venue's page of the Trade mode
(`ui-presentation-rule.md` §5), without an exchange.

The Futures page laid out as a user sees it before the first read lands: an
empty chart, empty tables, the order entry waiting on the pair's terms. The
panels' own previews show them filled (`order_entry/`, `account_tabs/`,
`account_summary/`); the mode with both venues is `trade/preview.py`."""

from __future__ import annotations

from decimal import Decimal

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_summary import (
    FuturesAccountSummary,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    PositionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.position_side import (
    PositionSide,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_profile import (
    desk_profile_for,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_headline import (
    headline_figures,
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
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.position_row import (
    PositionRow,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


def build_preview() -> QWidget:
    view = DeskView(desk_profile_for(TradingVenue.FUTURES_TESTNET))
    fill_page(view)
    view.headline.show_figures(headline_figures(_summary(), _positions()))
    view.setWindowTitle("Trade — one venue")
    return view


def _summary() -> FuturesAccountSummary:
    """A funded account that is ahead: what the headline reads once the account is read."""
    return FuturesAccountSummary(
        venue=TradingVenue.FUTURES_TESTNET,
        available_balance=Decimal("8120.40"),
        equity=Decimal("10234.55"),
        wallet_balance=Decimal("10000.00"),
        margin_balance=Decimal("10234.55"),
        unrealized_pnl=Decimal("234.55"),
        position_mode=PositionMode.ONE_WAY,
    )


def _positions() -> tuple[PositionRow, ...]:
    """Two open positions, one 8% from its liquidation price."""
    return tuple(
        PositionRow(
            symbol=symbol,
            side=side,
            quantity=Decimal("0.5"),
            entry_price=entry,
            mark_price=mark,
            unrealized_pnl=pnl,
            leverage=10,
            liquidation_price=liquidation,
        )
        for symbol, side, entry, mark, pnl, liquidation in (
            (
                "BTCUSDT",
                PositionSide.LONG,
                Decimal(60000),
                Decimal(62000),
                Decimal(1000),
                Decimal(57040),
            ),
            (
                "ETHUSDT",
                PositionSide.SHORT,
                Decimal(3000),
                Decimal(3050),
                Decimal(-25),
                Decimal(3600),
            ),
        )
    )


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
