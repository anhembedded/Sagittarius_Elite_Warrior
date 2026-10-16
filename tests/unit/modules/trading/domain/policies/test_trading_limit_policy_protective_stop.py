"""`EPIC-039L` — a Futures owner's protective stop is not paced like a new trade.

@details A bot's ladder fills and re-lays orders every few hundred milliseconds. A stop placed
at the opening fill meets the spacing, the rate window and the open-order count that the
ladder has just used, and being refused for them would leave the position bare. A reducing
purpose therefore passes those three for a position owner; the same facts as an entry still
fail them (the exemption is the purpose), and a Spot owner, which has no position, is judged
as before."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_purpose import (
    OrderPurpose,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    EMPTY_INVENTORY,
    FuturesLimits,
    OwnerBudget,
    OwnerBudgetFacts,
    PositionExposure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_position import (
    OwnerPosition,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trading_limits import (
    DEFAULT_TRADING_LIMITS,
    TradingLimitContext,
    TradingLimitViolation,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.trading_limit_policy import (
    TradingLimitPolicy,
)

_BUDGET = OwnerBudget(
    10,
    Decimal(1000),
    timedelta(milliseconds=250),
    60,
    timedelta(minutes=1),
    futures=FuturesLimits(Decimal(5000), 5, Decimal(1000)),
)
_POSITION = PositionExposure(
    OwnerPosition(Decimal(2), Decimal(100), Decimal(0), Decimal(0)),
    Decimal(0),
    Decimal(0),
    Decimal(0),
    Decimal(0),
    order_reduce_only=False,
)
#: The ladder is at every pacing ceiling: full of orders, just sent one, window used up.
_BUSY = OwnerBudgetFacts(
    budget=_BUDGET,
    open_order_count=10,
    open_buy_quote=Decimal(0),
    open_sell_quantity=Decimal(0),
    inventory=EMPTY_INVENTORY,
    time_since_last_order=timedelta(milliseconds=10),
    orders_in_window=60,
    order_side=OrderSide.SELL,
    order_quantity=Decimal(0),
    position=_POSITION,
)
_PACING = {
    TradingLimitViolation.OWNER_BUDGET_OPEN_ORDERS,
    TradingLimitViolation.OWNER_BUDGET_SPACING,
    TradingLimitViolation.OWNER_BUDGET_RATE,
}


def _failed(purpose: OrderPurpose, facts: OwnerBudgetFacts) -> set[object]:
    context = TradingLimitContext(
        orders_sent_this_session=0,
        order_notional=Decimal(0),
        open_position_count_for_symbol=1,
        time_since_last_order_for_symbol=None,
        purpose=purpose,
        client_order_tag="a3f9c1",
        owner_budget=facts,
    )
    checks = TradingLimitPolicy(DEFAULT_TRADING_LIMITS).evaluate(context)
    return {c.violation for c in checks if not c.passed}


@pytest.mark.parametrize("purpose", [OrderPurpose.PROTECTIVE, OrderPurpose.CLOSE])
def test_a_reducing_order_of_a_position_owner_passes_the_pacing_checks(
    purpose: OrderPurpose,
) -> None:
    assert _failed(purpose, _BUSY) == set()


def test_the_same_facts_as_an_entry_fail_every_pacing_check() -> None:
    assert _failed(OrderPurpose.ENTRY, _BUSY) == _PACING


def test_a_spot_owner_is_not_exempt_whatever_the_purpose() -> None:
    spot = replace(_BUSY, position=None)

    assert _failed(OrderPurpose.PROTECTIVE, spot) >= _PACING
