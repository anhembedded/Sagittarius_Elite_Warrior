"""A small ladder for the reaction tests: five levels 100, 110, 120, 130, 140,
buy quantity 1 each, step 0.001, with orders placed where a test asks."""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_reactions import (
    PlaceOrder,
    accepted,
    placed,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridRuntime,
    RuntimeLevel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide

STEP = Decimal("0.001")
PRICES = (Decimal(100), Decimal(110), Decimal(120), Decimal(130), Decimal(140))


def empty_ladder() -> GridRuntime:
    return GridRuntime(
        tuple(
            RuntimeLevel(index, price, Decimal(1)) for index, price in enumerate(PRICES)
        )
    )


def order_id(index: int) -> str:
    return f"SEW-a3f9c1-{index:010d}"


def resting(
    runtime: GridRuntime,
    index: int,
    side: OrderSide,
    quantity: Decimal = Decimal(1),
    paired_buy_price: Decimal | None = None,
) -> GridRuntime:
    action = PlaceOrder(index, side, PRICES[index], quantity, paired_buy_price)
    return accepted(placed(runtime, action, order_id(index)), order_id(index))


def perform(runtime: GridRuntime, action: PlaceOrder) -> GridRuntime:
    """What the executor does with a `PlaceOrder`: send it under the level's id
    and see it accepted."""
    oid = order_id(action.level_index)
    return accepted(placed(runtime, action, oid), oid)


def started_ladder() -> GridRuntime:
    """BUYs at L0 and L1, the gap at L2, SELLs at L3 and L4 (opening-bought)."""
    runtime = empty_ladder()
    runtime = resting(runtime, 0, OrderSide.BUY)
    runtime = resting(runtime, 1, OrderSide.BUY)
    runtime = resting(runtime, 3, OrderSide.SELL)
    return resting(runtime, 4, OrderSide.SELL)
