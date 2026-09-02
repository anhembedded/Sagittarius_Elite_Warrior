from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.domain.events.order_filled_event import (
    OrderFilledEvent,
)
from Sagittarius_Elite_Warrior.src.domain.trading.client_order_id import ClientOrderId
from Sagittarius_Elite_Warrior.src.domain.trading.order import Order
from Sagittarius_Elite_Warrior.src.domain.trading.order_type import OrderType
from Sagittarius_Elite_Warrior.src.domain.value_objects.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.presentation.ui.common.order_fill_marker import (
    order_filled_marker,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.theme import (
    BEAR_COLOR,
    BULL_COLOR,
)


def _order(side: OrderSide, reduce_only: bool = False, order_time=None) -> Order:
    return Order(
        client_order_id=ClientOrderId("SEW-a91f4c72e0b8"),
        symbol="BTCUSDT",
        side=side,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.05"),
        reduce_only=reduce_only,
        order_time=order_time,
    )


def _event(**overrides) -> OrderFilledEvent:
    defaults = {
        "order": _order(OrderSide.BUY),
        "fill_price": Decimal("64000.00"),
        "fill_quantity": Decimal("0.05"),
    }
    defaults.update(overrides)
    return OrderFilledEvent(**defaults)


def test_a_buy_fill_is_a_green_up_marker() -> None:
    marker = order_filled_marker(_event(order=_order(OrderSide.BUY)))

    _, price, label, color, direction = marker
    assert price == 64000.0
    assert label == "MUA"
    assert color == BULL_COLOR
    assert direction == "up"


def test_a_sell_fill_is_a_red_down_marker() -> None:
    marker = order_filled_marker(_event(order=_order(OrderSide.SELL)))

    _, _, label, color, direction = marker
    assert label == "BÁN"
    assert color == BEAR_COLOR
    assert direction == "down"


def test_a_reduce_only_fill_is_labelled_as_closing() -> None:
    marker = order_filled_marker(_event(order=_order(OrderSide.SELL, reduce_only=True)))

    assert marker[2] == "BÁN (Đóng)"


def test_uses_the_orders_own_fill_time_when_present() -> None:
    fill_time = datetime(2026, 9, 2, 12, 30, tzinfo=UTC)
    marker = order_filled_marker(
        _event(order=_order(OrderSide.BUY, order_time=fill_time))
    )

    assert marker[0] == fill_time.timestamp()


def test_falls_back_to_now_when_order_time_is_missing() -> None:
    before = datetime.now(UTC).timestamp()
    marker = order_filled_marker(_event(order=_order(OrderSide.BUY, order_time=None)))
    after = datetime.now(UTC).timestamp()

    assert before <= marker[0] <= after
