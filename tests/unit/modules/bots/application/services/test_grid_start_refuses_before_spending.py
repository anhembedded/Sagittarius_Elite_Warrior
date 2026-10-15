"""`BUG-212` - a start whose ladder the exchange would refuse spends nothing.

The owner's Spot MAINNET start (2348-2667, 7 grids, 35 USDT, price 2363.77, step 0.0001,
minimum notional 5): the opening market buy went out, and only then did the first SELL come back
`min_notional` - 0.002 x 2393.58 = 4.79. The real `GridExecutor` is started on a simulated venue;
the order book records every request it sends.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    GridWorld,
    grid_world,
)

D = Decimal
_OWNER = {
    "lower": "2348",
    "upper": "2667",
    "grid_count": "7",
    "spacing": "ARITHMETIC",
    "capital_quote": "35",
    "stop_loss": "price:2259",
    "take_profit": "price:2805",
}


def _world(**changes: str) -> GridWorld:
    return grid_world(
        config={**_OWNER, **changes}, step=D("0.0001"), last_price=D("2363.77")
    )


def test_the_owners_start_is_refused_before_any_order_is_sent() -> None:
    world = _world()

    world.executor.start()

    assert world.book.requests == [], "no market buy may precede a refused ladder"
    assert world.state() is BotLifecycleState.HALTED
    assert world.runtime().reason is GridReason.START_REFUSED
    detail = world.runtime().reason_detail
    assert "L1 SELL" in detail
    assert "4.79" in detail
    assert "minimum of 5" in detail
    assert "fewer grids" in detail


def test_a_plan_that_clears_the_minimum_still_starts() -> None:
    world = _world(capital_quote="100")

    world.executor.start()

    assert world.state() is BotLifecycleState.RUNNING
    (opening, *ladder) = world.book.requests
    assert opening.order_type is OrderType.MARKET
    assert ladder
    assert all(r.quantity * r.reference_price >= 5 for r in ladder)


@pytest.mark.parametrize("capital", ["35", "38", "45", "60", "80", "100", "300"])
@pytest.mark.parametrize("grids", ["5", "7", "9"])
def test_whatever_the_executor_sends_meets_the_exchange_minimum(
    capital: str, grids: str
) -> None:
    """A start either sends nothing, or sends a ladder every order of which the exchange takes."""
    world = _world(capital_quote=capital, grid_count=grids)

    world.executor.start()

    limits = [r for r in world.book.requests if r.order_type is OrderType.LIMIT]
    if world.state() is BotLifecycleState.RUNNING:
        assert limits
        assert all(r.quantity * r.reference_price >= 5 for r in limits)
    else:
        assert world.book.requests == []
