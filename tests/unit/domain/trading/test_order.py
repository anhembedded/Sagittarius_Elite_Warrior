import dataclasses
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.domain.trading.client_order_id import (
    generate_client_order_id,
)
from Sagittarius_Elite_Warrior.src.domain.trading.order import Order
from Sagittarius_Elite_Warrior.src.domain.trading.order_status import OrderStatus
from Sagittarius_Elite_Warrior.src.domain.trading.order_type import OrderType
from Sagittarius_Elite_Warrior.src.domain.value_objects.order_side import OrderSide


def _order(**overrides: object) -> Order:
    defaults: dict[str, object] = {
        "client_order_id": generate_client_order_id(),
        "symbol": "BTCUSDT",
        "side": OrderSide.BUY,
        "order_type": OrderType.MARKET,
        "quantity": Decimal("0.013"),
    }
    defaults.update(overrides)
    return Order(**defaults)  # type: ignore[arg-type]


def test_order_defaults_to_new_status() -> None:
    assert _order().status is OrderStatus.NEW


def test_order_defaults_have_no_limit_or_stop_fields() -> None:
    order = _order()
    assert order.price is None
    assert order.stop_price is None
    assert order.time_in_force is None
    assert order.reduce_only is False


def test_order_is_frozen() -> None:
    order = _order()
    with pytest.raises(dataclasses.FrozenInstanceError):
        order.status = OrderStatus.FILLED  # type: ignore[misc]
