"""`EPIC-028O` — a stop waits for the market only from the trigger side.

@details Boundary value analysis on the stop price around the last price,
for each side: one tick below, equal, one tick above.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.stop_price_check import (
    StopPriceCheck,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.stop_trigger_side import (
    check_stop_trigger_side,
    check_trigger_side,
    waits_above_market,
)

_LAST = Decimal("50000.00")
_TICK = Decimal("0.01")


@pytest.mark.parametrize(
    ("side", "stop", "verdict"),
    [
        (OrderSide.BUY, _LAST + _TICK, StopPriceCheck.ON_TRIGGER_SIDE),
        (OrderSide.BUY, _LAST, StopPriceCheck.WRONG_SIDE),
        (OrderSide.BUY, _LAST - _TICK, StopPriceCheck.WRONG_SIDE),
        (OrderSide.SELL, _LAST - _TICK, StopPriceCheck.ON_TRIGGER_SIDE),
        (OrderSide.SELL, _LAST, StopPriceCheck.WRONG_SIDE),
        (OrderSide.SELL, _LAST + _TICK, StopPriceCheck.WRONG_SIDE),
    ],
    ids=[
        "buy-above",
        "buy-at",
        "buy-below",
        "sell-below",
        "sell-at",
        "sell-above",
    ],
)
def test_a_stop_waits_only_from_its_trigger_side(
    side: OrderSide, stop: Decimal, verdict: StopPriceCheck
) -> None:
    assert check_stop_trigger_side(side, stop, _LAST) is verdict


@pytest.mark.parametrize(
    ("side", "trigger", "verdict"),
    [
        (OrderSide.SELL, _LAST + _TICK, StopPriceCheck.ON_TRIGGER_SIDE),
        (OrderSide.SELL, _LAST, StopPriceCheck.WRONG_SIDE),
        (OrderSide.SELL, _LAST - _TICK, StopPriceCheck.WRONG_SIDE),
        (OrderSide.BUY, _LAST - _TICK, StopPriceCheck.ON_TRIGGER_SIDE),
        (OrderSide.BUY, _LAST, StopPriceCheck.WRONG_SIDE),
        (OrderSide.BUY, _LAST + _TICK, StopPriceCheck.WRONG_SIDE),
    ],
    ids=["sell-above", "sell-at", "sell-below", "buy-below", "buy-at", "buy-above"],
)
def test_a_take_profit_waits_on_the_side_opposite_a_stop(
    side: OrderSide, trigger: Decimal, verdict: StopPriceCheck
) -> None:
    """`EPIC-028I` — a long's take-profit sells above the market."""
    assert (
        check_trigger_side(OrderType.TAKE_PROFIT_MARKET, side, trigger, _LAST)
        is verdict
    )


@pytest.mark.parametrize("order_type", [OrderType.STOP_LIMIT, OrderType.STOP_MARKET])
def test_every_other_triggered_type_follows_the_stop_rule(
    order_type: OrderType,
) -> None:
    assert (
        check_trigger_side(order_type, OrderSide.SELL, _LAST - _TICK, _LAST)
        is StopPriceCheck.ON_TRIGGER_SIDE
    )


@pytest.mark.parametrize(
    ("order_type", "side", "above"),
    [
        (OrderType.STOP_MARKET, OrderSide.BUY, True),
        (OrderType.STOP_MARKET, OrderSide.SELL, False),
        (OrderType.TAKE_PROFIT_MARKET, OrderSide.SELL, True),
        (OrderType.TAKE_PROFIT_MARKET, OrderSide.BUY, False),
    ],
)
def test_which_triggers_wait_above_the_market(
    order_type: OrderType, side: OrderSide, above: bool
) -> None:
    assert waits_above_market(order_type, side) is above
