"""`EPIC-044C` (ADR 044 D10) - the entry path publishes one `BotRangeEnteredEvent`, once the ladder is laid.

The entry is two transitions, so the alert is not built from a state change: the bot says it itself,
only when the wait ended in a running ladder.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_range_entered_event import (
    BotRangeEnteredEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderSafetyGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRefusal,
    OwnerBudgetRegistrationResult,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.waiting_world import (
    ABOVE,
    BELOW,
    CASES,
    INSIDE,
    a_wait,
    started,
)

S = BotLifecycleState


def _told(case) -> list[BotRangeEnteredEvent]:  # type: ignore[no-untyped-def]
    return [
        event
        for event in case.world.events.events
        if isinstance(event, BotRangeEnteredEvent)
    ]


@pytest.mark.parametrize(("market", "direction", "price"), CASES)
def test_an_entry_tells_once_with_the_price_the_range_and_the_orders_laid(
    market: str, direction: str, price: Decimal
) -> None:
    case = started(a_wait(market, direction, price))
    assert _told(case) == [], "nothing is told while the bot waits"

    case.price_is(INSIDE)

    [event] = _told(case)
    assert case.world.state() is S.RUNNING
    assert event.price == INSIDE
    assert (event.lower, event.upper) == (Decimal(100), Decimal(140))
    assert event.orders == len(case.world.runtime().open_orders)
    assert event.orders > 0


def test_a_price_that_stays_inside_after_the_entry_tells_nothing_more() -> None:
    case = started(a_wait("spot", "LONG", BELOW))
    case.price_is(INSIDE)
    case.world.monotonic.advance(60)

    case.price_is(INSIDE + 1)

    assert len(_told(case)) == 1


def test_a_start_inside_the_range_tells_nothing() -> None:
    case = started(a_wait("spot", "LONG", INSIDE))

    assert case.world.state() is S.RUNNING
    assert _told(case) == []


def test_an_entry_the_plan_refuses_tells_nothing() -> None:
    case = started(a_wait("spot", "LONG", ABOVE))
    case.world.session.register_owner_budget_answers(
        OwnerBudgetRegistrationResult(
            OwnerBudgetRefusal.ABOVE_GLOBAL_CAP, exceeded_cap="max_total"
        )
    )

    case.price_is(INSIDE)

    assert case.world.state() is S.HALTED
    assert _told(case) == []


def test_an_entry_whose_ladder_cannot_be_laid_tells_nothing() -> None:
    """The start sequence meets a refused key after `range_entered`: the halt has its own alert."""
    case = started(a_wait("spot", "LONG", BELOW))
    case.world.book.refuse_next = [ExecuteOrderSafetyGate.KEY_REJECTED]

    case.price_is(INSIDE)

    assert case.world.state() is S.HALTED
    assert _told(case) == []
