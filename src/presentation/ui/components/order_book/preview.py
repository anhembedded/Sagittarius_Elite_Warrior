"""Standalone preview of the order-book tables (`ui-presentation-rule.md`).

Both panels side by side with rows that cover what a reviewer needs to see
without a running exchange: a long and a short position, a profit and a loss,
a limit order with a price and a market order without one.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from PySide6.QtWidgets import QHBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.live_position import (
    LivePosition,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    OrderStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.presentation.ui.components.order_book.open_order_row import (
    build_open_order_row,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.order_book.open_orders_panel import (
    OpenOrdersPanel,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.order_book.position_row import (
    build_position_row,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.order_book.positions_panel import (
    PositionsPanel,
)

_NOW = datetime(2026, 9, 15, 9, 30, tzinfo=UTC)


def _position(symbol: str, amt: str, pnl: str, liquidation: str | None) -> LivePosition:
    return LivePosition(
        symbol=symbol,
        position_amt=Decimal(amt),
        entry_price=Decimal("64000.00"),
        mark_price=Decimal("64512.50"),
        unrealized_pnl=Decimal(pnl),
        leverage=10,
        margin_type=MarginType.CROSSED,
        liquidation_price=Decimal(liquidation) if liquidation else None,
        updated_at=_NOW,
    )


def _order(
    symbol: str,
    side: OrderSide,
    order_type: OrderType,
    price: str | None,
    order_id: str,
) -> Order:
    return Order(
        client_order_id=ClientOrderId(order_id),
        symbol=symbol,
        side=side,
        order_type=order_type,
        quantity=Decimal("0.2500"),
        price=Decimal(price) if price else None,
        status=OrderStatus.NEW,
        order_time=_NOW,
    )


def build_preview() -> QWidget:
    """Builds a standalone preview of the two order-book panels."""
    positions = PositionsPanel()
    positions.set_rows(
        [
            build_position_row(_position("BTCUSDT", "0.5", "512.25", "58120.00")),
            build_position_row(_position("ETHUSDT", "-4.0", "-88.40", None)),
        ]
    )

    open_orders = OpenOrdersPanel()
    open_orders.set_rows(
        [
            build_open_order_row(
                _order("BTCUSDT", OrderSide.BUY, OrderType.LIMIT, "63000.00", "sew-1")
            ),
            build_open_order_row(
                _order("ETHUSDT", OrderSide.SELL, OrderType.MARKET, None, "sew-2")
            ),
        ]
    )

    host = QWidget()
    row = QHBoxLayout(host)
    row.addWidget(positions, 1)
    row.addWidget(open_orders, 1)
    host.resize(1100, 320)
    return host
