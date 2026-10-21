"""`EPIC-044C` — a bot waiting for its range keeps the last price it heard.

The Plan says "Waiting for the price to enter X-Y (last price Z)" and `bot show` the price position,
both from the run's last price (`BotProgress.mark_price`). A waiting bot watches no exit, so
without this the price the bot waits on was the one number it never recorded.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.waiting_world import (
    ABOVE,
    BELOW,
    CASES,
    a_wait,
    started,
)

S = BotLifecycleState


@pytest.mark.parametrize(("market", "direction", "price"), CASES)
def test_a_waiting_bot_records_the_price_it_hears(
    market: str, direction: str, price: Decimal
) -> None:
    case = started(a_wait(market, direction, price))
    heard = price - 1 if price < BELOW + 1 else price + 1

    case.price_is(heard)

    assert case.world.state() is S.AWAITING_RANGE
    runtime = case.world.runtime()
    assert runtime.mark_price == heard
    assert runtime.mark_price_at is not None


def test_the_recorded_price_follows_the_market_while_the_bot_waits() -> None:
    case = started(a_wait("spot", "LONG", BELOW))
    case.price_is(BELOW - 2)
    case.world.monotonic.advance(60)

    case.price_is(ABOVE + 2)

    assert case.world.runtime().mark_price == ABOVE + 2
