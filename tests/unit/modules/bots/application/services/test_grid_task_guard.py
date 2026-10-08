"""`EPIC-035C` (H4) — a task that placed orders and ended HALTED or ERROR parks the ladder.

`GridTaskGuard` used to park only on a *transition into* HALTED or ERROR. A
confirmed resume starts in HALTED, places part of the ladder, and is refused
part-way: HALTED → STARTING → HALTED. The guard saw HALTED before and HALTED
after, did not park, and the placed part of the ladder kept trading under a bot
that no longer managed it. The rule is now "the task sent orders, or the bot
fell into HALTED or ERROR": parked state is inferred from the fact that orders
may rest, not from a state change.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_order_events import (
    BotOrderEnd,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.trading_switch_changed_event import (
    TradingSwitchCause,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trading_limits import (
    TradingLimitViolation,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    GridWorld,
    grid_world,
)

S = BotLifecycleState
_REFUSED = TradingLimitViolation.OWNER_BUDGET_RATE


def _halted_with_a_proposal() -> GridWorld:
    """Emergency Stop left the ladder resting; resume cancelled it and proposed
    a new one that awaits the user's confirmation."""
    world = grid_world()
    world.executor.start()
    world.executor.on_switch(False, TradingSwitchCause.EMERGENCY_STOP)
    world.derive("4.132", cost="499.97")
    world.executor.resume()
    assert world.state() is S.HALTED
    assert world.executor.proposal is not None
    assert world.book.open == {}
    world.book.cancels.clear()
    return world


def _confirm_refused_part_way() -> GridWorld:
    world = _halted_with_a_proposal()
    world.book.refuse_next = [None, None, _REFUSED]
    world.executor.confirm_resume()
    return world


def _start_refused_part_way() -> GridWorld:
    world = grid_world()
    # Two opening slices and one ladder order are accepted, the next refused.
    world.book.refuse_next = [None, None, None, _REFUSED]
    world.executor.start()
    return world


def _counter_order_faulted() -> GridWorld:
    world = grid_world()
    world.executor.start()
    world.book.raise_next = [ConnectionError("read timed out")]
    world.fill(Decimal(110), "2.272")
    return world


def _replace_faulted() -> GridWorld:
    world = grid_world()
    world.executor.start()
    oid = world.open_ids_by_price()[Decimal(140)]
    world.book.open.pop(oid)
    world.book.raise_next = [ConnectionError("read timed out")]
    world.executor.on_end(BotOrderEnd(oid))
    return world


def test_a_confirm_resume_refused_part_way_parks_the_partial_ladder() -> None:
    world = _confirm_refused_part_way()

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.START_REFUSED
    assert world.book.submitted, "the confirmed ladder was part-way placed"
    assert world.book.open == {}, "the part that was placed must not keep resting"
    assert world.runtime().open_orders == ()
    assert len(world.book.cancels) == 2


@pytest.mark.parametrize(
    "scenario",
    [
        pytest.param(_start_refused_part_way, id="start"),
        pytest.param(_confirm_refused_part_way, id="resume-confirm"),
        pytest.param(_counter_order_faulted, id="counter-order"),
        pytest.param(_replace_faulted, id="re-place"),
    ],
)
def test_every_task_that_places_is_parked_when_it_ends_halted_or_error(
    scenario: Callable[[], GridWorld],
) -> None:
    world = scenario()

    assert world.state() in (S.HALTED, S.ERROR)
    assert world.book.open == {}
    assert world.runtime().open_orders == ()


def test_a_parked_bot_is_not_cancelled_again_by_every_task() -> None:
    world = _confirm_refused_part_way()
    cancels_after_park = len(world.book.cancels)
    reads_after_park = world.activity.open_order_reads

    for price in ("120", "121", "122"):
        world.executor.on_tick(Decimal(price))
    world.executor.on_end(BotOrderEnd("not-this-bots-order"))

    assert len(world.book.cancels) == cancels_after_park
    assert world.activity.open_order_reads == reads_after_park, (
        "a parked bot's tasks must not read the book to park again"
    )


def test_a_request_that_raised_from_halted_still_parks_the_ladder() -> None:
    """HALTED → STARTING → ERROR: before and after are both parked states, so
    only "the task sent an order" says the raised request may be resting. The
    gateway counts a request that raised for exactly this."""
    world = _halted_with_a_proposal()
    reads_before = world.activity.open_order_reads
    world.book.raise_next = [ConnectionError("read timed out")]

    world.executor.confirm_resume()

    assert world.state() is S.ERROR
    assert world.activity.open_order_reads > reads_before, "the ladder was parked"
