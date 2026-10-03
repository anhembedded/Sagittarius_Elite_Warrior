"""`EPIC-028J` — the orders, positions and history rows the account-tab
tests share, so each test states only what it changes."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_record import (
    OrderRecord,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    OrderStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trade_record import (
    TradeRecord,
)

NOW = datetime(2026, 10, 1, 12, tzinfo=UTC)


def order(symbol: str = "BTCUSDT", client_order_id: str = "SEW-btc") -> Order:
    return Order(
        client_order_id=ClientOrderId(client_order_id),
        symbol=symbol,
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("0.01"),
        status=OrderStatus.NEW,
        price=Decimal(59000),
        order_time=NOW,
    )


def position(symbol: str = "BTCUSDT", amount: str = "0.02") -> LivePosition:
    return LivePosition(
        symbol=symbol,
        position_amt=Decimal(amount),
        entry_price=Decimal(60000),
        mark_price=Decimal(60100),
        unrealized_pnl=Decimal(2),
        leverage=10,
        margin_type=MarginType.CROSSED,
        liquidation_price=None,
        updated_at=NOW,
    )


def order_record(symbol: str = "BTCUSDT") -> OrderRecord:
    return OrderRecord(
        order=order(symbol, f"SEW-{symbol.lower()}"),
        executed_quantity=Decimal(0),
        average_price=None,
        created_at=NOW,
        exchange_order_id=1,
    )


def trade_record(symbol: str = "BTCUSDT", trade_id: int = 1) -> TradeRecord:
    return TradeRecord(
        symbol=symbol,
        trade_id=trade_id,
        order_id=trade_id,
        side=OrderSide.BUY,
        price=Decimal(60000),
        quantity=Decimal("0.01"),
        quote_quantity=Decimal(600),
        fee=Decimal("0.24"),
        fee_asset="USDT",
        time=NOW,
        realized_pnl=Decimal(0),
    )
