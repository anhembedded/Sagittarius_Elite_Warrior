"""`EPIC-039D` - the shared fixtures of the Futures owner-position tests: a
registration, orders and trades in the shapes the venue's history returns."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    FuturesLimits,
    OwnerBudget,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRegistration,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trade_record import (
    TradeRecord,
)

NOW = datetime.now(UTC)
RUN = NOW - timedelta(days=1)
TAG = "f0a1b2"
STEP = Decimal("0.001")
BUDGET = OwnerBudget(
    10,
    Decimal(100_000),
    timedelta(milliseconds=250),
    60,
    timedelta(minutes=1),
    futures=FuturesLimits(Decimal(50_000), 10, Decimal(5_000)),
)
REGISTRATION = OwnerBudgetRegistration("bot-f0", TAG, "BTCUSDT", RUN, BUDGET)


def order(
    number: int,
    side: OrderSide = OrderSide.BUY,
    quantity: str = "0.010",
    *,
    client_order_id: str | None = None,
    reduce_only: bool = False,
    status: OrderStatus = OrderStatus.NEW,
) -> Order:
    return Order(
        client_order_id=ClientOrderId(client_order_id or f"SEW-{TAG}-{number:010x}"),
        symbol="BTCUSDT",
        side=side,
        order_type=OrderType.LIMIT,
        quantity=Decimal(quantity),
        price=Decimal(60000),
        status=status,
        reduce_only=reduce_only,
    )


def traded(
    number: int,
    side: OrderSide,
    quantity: str,
    price: str,
    *,
    fee: str = "0",
    fee_asset: str = "USDT",
    client_order_id: str | None = None,
) -> tuple[OrderRecord, TradeRecord]:
    """An order of the venue's history and its one fill; `number` is both ids."""
    placed = order(number, side, quantity, client_order_id=client_order_id)
    record = OrderRecord(
        placed,
        Decimal(quantity),
        Decimal(price),
        RUN + timedelta(hours=number),
        number,
    )
    trade = TradeRecord(
        symbol="BTCUSDT",
        trade_id=1000 + number,
        order_id=number,
        side=side,
        price=Decimal(price),
        quantity=Decimal(quantity),
        quote_quantity=Decimal(quantity) * Decimal(price),
        fee=Decimal(fee),
        fee_asset=fee_asset,
        time=RUN + timedelta(hours=number, minutes=1),
    )
    return record, trade
