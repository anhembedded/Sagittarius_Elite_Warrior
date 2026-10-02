"""Standalone preview of a desk's account tabs (`ui-presentation-rule.md`
§5), without an exchange.

The Futures layout, so the Positions tab and its "Close at market" action
show: two open orders on two pairs, one losing position, and an order
history read across three pairs with one notice beside it. "Hide other
pairs" is off, so every pair shows and the scope line names them."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.history_page import (
    HistoryPage,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.live_position import (
    LivePosition,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_record import (
    OrderRecord,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    OrderStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_tabs.account_tabs_panel import (
    AccountTabsPanel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_tabs.history_rows import (
    build_order_history_row,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_tabs.history_view import (
    HistoryKind,
    history_view_for,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_profile import (
    HeldTab,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.open_order_row import (
    build_open_order_row,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.position_row import (
    build_position_row,
)

_AT = datetime(2026, 10, 1, 9, 30, tzinfo=UTC)


def _order(symbol: str, side: OrderSide, price: str, status: OrderStatus) -> Order:
    return Order(
        client_order_id=ClientOrderId(f"SEW-{symbol.lower()}"),
        symbol=symbol,
        side=side,
        order_type=OrderType.LIMIT,
        quantity=Decimal("0.010"),
        status=status,
        price=Decimal(price),
        order_time=_AT,
    )


def build_preview() -> QWidget:
    panel = AccountTabsPanel(HeldTab.POSITIONS)
    panel.set_desk_symbol("BTCUSDT")
    panel.set_open_orders(
        [
            build_open_order_row(
                _order("BTCUSDT", OrderSide.BUY, "59000", OrderStatus.NEW)
            ),
            build_open_order_row(
                _order("ETHUSDT", OrderSide.SELL, "2650", OrderStatus.NEW)
            ),
        ]
    )
    panel.set_positions(
        [
            build_position_row(
                LivePosition(
                    symbol="BTCUSDT",
                    position_amt=Decimal("0.020"),
                    entry_price=Decimal(60500),
                    mark_price=Decimal("60123.45"),
                    unrealized_pnl=Decimal("-7.53"),
                    leverage=10,
                    margin_type=MarginType.CROSSED,
                    liquidation_price=None,
                    updated_at=_AT,
                )
            )
        ]
    )
    history = HistoryPage(
        rows=(
            OrderRecord(
                order=_order("BTCUSDT", OrderSide.BUY, "60500", OrderStatus.FILLED),
                executed_quantity=Decimal("0.020"),
                average_price=Decimal(60500),
                created_at=_AT,
            ),
        ),
        page=0,
        total_rows=1,
        scanned_symbols=("BTCUSDT", "ETHUSDT", "SOLUSDT"),
        notices=("Conditional orders older than seven days are not listed.",),
    )
    panel.show_history(
        HistoryKind.ORDERS, history_view_for(history, build_order_history_row)
    )
    panel.setWindowTitle("Account tabs — Futures")
    return panel
