"""`BUG-276`, slice 1 (ADR `DECISION_2026-10-27`, D6) - a waiting Grid keeps the best price it saw.

The bot judges its trigger on samples, so a wick between two samples can touch the trigger and
leave no trace (the owner's bot `ixr5v8`). The best price heard while waiting - the lowest for a
bot that wants a lower price, the highest for one that wants a higher - is kept with the record, so
the screen can say whether the price touched the trigger. It places nothing and enters nothing.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_price_tick import (
    PriceTick,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridRuntime,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    grid_world,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.waiting_world import (
    WITH_NO_EXITS,
    Wait,
    a_wait,
    started,
)

D = Decimal
S = BotLifecycleState
_TRIGGERED = {**WITH_NO_EXITS, "trigger_price": "125"}
_BAR = datetime(2026, 10, 27, 7, 30, tzinfo=UTC)
#: Waiting short of the trigger, a price still short of it, then a wick-sized dip past it.
_CASES = [
    pytest.param("spot", "LONG", D(135), id="spot-long"),
    pytest.param("futures", "LONG", D(135), id="futures-long"),
]


def _stream_tick(case: Wait, last: Decimal, low: Decimal, high: Decimal) -> None:
    """A kline update: the close now, and the bar's extremes so far."""
    case.world.monotonic.advance(10)
    case.world.executor.facts.on_tick(PriceTick(last, low, high, _BAR))


@pytest.mark.parametrize(("market", "direction", "start"), _CASES)
def test_the_lowest_price_heard_while_waiting_is_kept(
    market: str, direction: str, start: Decimal
) -> None:
    case = started(a_wait(market, direction, start, config=_TRIGGERED))

    case.price_is(D(131))
    case.price_is(D(128))
    case.price_is(D(130))

    assert case.world.state() is S.AWAITING_RANGE
    assert case.world.runtime().waiting_best_price == D(128)


def test_a_short_keeps_the_highest_price() -> None:
    case = started(a_wait("futures", "SHORT", D(115), config=_TRIGGERED))

    case.price_is(D(119))
    case.price_is(D(122))
    case.price_is(D(118))

    assert case.world.runtime().waiting_best_price == D(122)


def test_a_wick_the_stream_carried_between_two_samples_is_kept_though_it_entered_nothing() -> (
    None
):
    """The owner's case on Spot: the bar's low went through the trigger, the close did not."""
    case = started(a_wait("spot", "LONG", D(135), config=_TRIGGERED))
    _stream_tick(case, last=D(135), low=D(134), high=D(136))

    _stream_tick(case, last=D(131), low=D(124), high=D(136))

    assert case.world.state() is S.AWAITING_RANGE, "a wick is evidence, not an entry"
    assert case.world.book.requests == []
    assert case.world.runtime().waiting_best_price == D(124)


def test_a_wick_from_before_the_bot_listened_is_not_kept() -> None:
    """`BUG-191`: the first update of a run counts by its close only."""
    case = started(a_wait("spot", "LONG", D(135), config=_TRIGGERED))

    _stream_tick(case, last=D(135), low=D(110), high=D(136))

    assert case.world.runtime().waiting_best_price == D(135)


def test_a_restart_keeps_the_best_price_the_record_already_holds() -> None:
    """The review of #748: a fresh memory must start from the saved best, or the first close after
    a restart would overwrite 128 with 131 and the screen would say the price never touched it."""
    world = grid_world(
        state=S.AWAITING_RANGE,
        runtime=replace(GridRuntime(()), waiting_best_price=D(128)),
        config=_TRIGGERED,
        last_price=D(131),
    )
    case = Wait(world, None)

    case.price_is(D(131))

    assert world.runtime().waiting_best_price == D(128)


def test_a_restart_still_improves_on_the_saved_best() -> None:
    world = grid_world(
        state=S.AWAITING_RANGE,
        runtime=replace(GridRuntime(()), waiting_best_price=D(128)),
        config=_TRIGGERED,
        last_price=D(131),
    )
    case = Wait(world, None)

    case.price_is(D(126))

    assert world.runtime().waiting_best_price == D(126)


@pytest.mark.parametrize("market", ["spot", "futures"])
def test_a_wait_with_no_trigger_keeps_and_writes_nothing(market: str) -> None:
    """Without a trigger the value is never shown, so the bot does not write it."""
    case = started(a_wait(market, "LONG", D(145), config=WITH_NO_EXITS))

    case.price_is(D(143))
    case.price_is(D(142))

    assert case.world.state() is S.AWAITING_RANGE
    assert case.world.runtime().waiting_best_price is None


@pytest.mark.parametrize(("market", "direction", "start"), _CASES)
def test_the_best_price_is_cleared_when_the_bot_leaves_the_wait(
    market: str, direction: str, start: Decimal
) -> None:
    """The review of #748, round 2: a low from this wait must not seed a later wait of the same
    record (a halted run resumed flat), where it would report a touch that never happened."""
    case = started(a_wait(market, direction, start, config=_TRIGGERED))
    case.price_is(D(128))
    assert case.world.runtime().waiting_best_price == D(128)

    case.price_is(D(124))
    assert case.world.state() is S.RUNNING
    case.price_is(D(124))

    assert case.world.runtime().waiting_best_price is None
