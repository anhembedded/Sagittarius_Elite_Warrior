"""`EPIC-028O` — a stop waits for the market only from the trigger side.

@details Boundary value analysis on the stop price around the last price,
for each side: one tick below, equal, one tick above.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.stop_price_check import (
    StopPriceCheck,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.stop_trigger_side import (
    check_stop_trigger_side,
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
