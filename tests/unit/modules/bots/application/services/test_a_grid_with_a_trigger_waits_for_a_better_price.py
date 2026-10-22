"""`EPIC-046A` - a Grid with a trigger price activates like a limit order (ADR 046 D1-D4).

The owner, 2026-10-22: the grid activates only when the price is better than the trigger. The range
is 100-140 and the trigger 125: a LONG waits inside the range until the price is at or below it, a
SHORT until it is at or above it. These tests drive the real executor over the simulated venue,
through the same AWAITING_RANGE wait `EPIC-044` built, and assert what the venue was asked.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_price_tick import (
    PriceTick,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridRuntime,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    BOT,
    grid_world,
    quote_at,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.waiting_world import (
    WITH_NO_EXITS,
    a_wait,
    started,
)

D = Decimal
S = BotLifecycleState
_TRIGGERED = {**WITH_NO_EXITS, "trigger_price": "125"}
#: Short of the trigger, then better than it, for each side.
_CASES = [
    pytest.param("spot", "LONG", D(135), D(124), id="spot-long"),
    pytest.param("futures", "LONG", D(135), D(124), id="futures-long"),
    pytest.param("futures", "SHORT", D(115), D(126), id="futures-short"),
]


@pytest.mark.parametrize(("market", "direction", "short_of", "better"), _CASES)
def test_a_bot_inside_its_range_but_short_of_the_trigger_places_nothing_and_waits(
    market: str, direction: str, short_of: Decimal, better: Decimal
) -> None:
    case = started(a_wait(market, direction, short_of, config=_TRIGGERED))

    assert case.world.state() is S.AWAITING_RANGE
    assert case.world.book.requests == [], "nothing is sent to the exchange"


@pytest.mark.parametrize(("market", "direction", "short_of", "better"), _CASES)
def test_a_better_price_lays_what_a_normal_start_there_would(
    market: str, direction: str, short_of: Decimal, better: Decimal
) -> None:
    waiting = started(a_wait(market, direction, short_of, config=_TRIGGERED))
    normal = started(a_wait(market, direction, better))

    waiting.price_is(better)

    assert waiting.world.state() is S.RUNNING
    assert waiting.requests() == normal.requests()
    assert waiting.requests(), "a ladder was laid"


@pytest.mark.parametrize(("market", "direction", "short_of", "better"), _CASES)
def test_a_price_still_short_of_the_trigger_does_not_enter(
    market: str, direction: str, short_of: Decimal, better: Decimal
) -> None:
    case = started(a_wait(market, direction, short_of, config=_TRIGGERED))

    case.price_is(short_of + (D(5) if direction == "LONG" else D(-5)))

    assert case.world.state() is S.AWAITING_RANGE
    assert case.world.book.requests == []


@pytest.mark.parametrize("direction", ["LONG", "SHORT"])
def test_a_price_exactly_on_the_trigger_enters(direction: str) -> None:
    short_of = D(135) if direction == "LONG" else D(115)
    case = started(a_wait("futures", direction, short_of, config=_TRIGGERED))

    case.price_is(D(125))

    assert case.world.state() is S.RUNNING


def test_a_long_whose_trigger_is_already_met_at_start_activates_at_once() -> None:
    case = started(a_wait("spot", "LONG", D(121), config=_TRIGGERED))

    assert case.world.state() is S.RUNNING
    assert case.requests() == started(a_wait("spot", "LONG", D(121))).requests()


def test_a_price_outside_the_range_never_enters_even_when_better_than_the_trigger() -> (
    None
):
    """99 is below a LONG's trigger of 125 but outside the range: the range is judged first."""
    case = started(a_wait("spot", "LONG", D(135), config=_TRIGGERED))

    case.price_is(D(99))

    assert case.world.state() is S.AWAITING_RANGE
    assert case.world.book.requests == []


@pytest.mark.parametrize(("market", "direction", "short_of", "better"), _CASES)
def test_once_triggered_the_bot_never_waits_again_when_the_price_moves_back(
    market: str, direction: str, short_of: Decimal, better: Decimal
) -> None:
    """D3: a filled limit order does not unfill."""
    case = started(a_wait(market, direction, short_of, config=_TRIGGERED))
    case.price_is(better)
    laid = len(case.world.book.requests)

    case.price_is(short_of)

    assert case.world.state() is S.RUNNING
    assert len(case.world.book.requests) >= laid


def test_a_restart_of_a_bot_that_triggered_resumes_running_not_waiting() -> None:
    """The latch is the state: RUNNING is restored through RECOVERING to RUNNING, whatever the
    price is against the trigger after the restart."""
    ran = grid_world(config=_TRIGGERED, last_price=D(121))
    ran.executor.start()
    assert ran.state() is S.RUNNING
    world = grid_world(
        state=S.RECOVERING,
        recovering_from=S.RUNNING,
        runtime=ran.runtime(),
        config=_TRIGGERED,
        last_price=D(135),
    )
    world.book.open = dict(ran.book.open)
    world.hold("0")

    world.executor.resume()

    assert world.state() is S.RUNNING
    world.executor.facts.on_tick(PriceTick.at(D(135)))
    assert world.state() is S.RUNNING


def test_a_restart_of_a_bot_still_short_of_its_trigger_keeps_waiting_for_it() -> None:
    world = grid_world(
        state=S.RECOVERING,
        recovering_from=S.AWAITING_RANGE,
        runtime=GridRuntime(()),
        config=_TRIGGERED,
        last_price=D(135),
    )
    world.hold("0")
    world.executor.resume()
    assert world.state() is S.AWAITING_RANGE

    quote_at(world, D(130))
    world.monotonic.advance(10)
    world.executor.facts.on_tick(PriceTick.at(D(130)))
    assert world.state() is S.AWAITING_RANGE, "130 is inside the range but above 125"

    quote_at(world, D(124))
    world.monotonic.advance(10)
    world.executor.facts.on_tick(PriceTick.at(D(124)))
    assert world.state() is S.RUNNING


def test_a_flat_bot_resumed_short_of_its_trigger_waits_for_it() -> None:
    """D3: a resume of a bot that holds nothing is a fresh entry, and the trigger is its limit."""
    world = grid_world(state=S.HALTED, last_price=D(135), config=_TRIGGERED)
    world.derive("0")

    world.executor.resume()

    assert world.state() is S.AWAITING_RANGE
    assert world.executor.proposal is None
    assert world.book.requests == []


def test_the_trigger_is_saved_with_the_bot() -> None:
    world = grid_world(config=_TRIGGERED, last_price=D(135))
    world.executor.start()

    saved = world.store.load(BotId(BOT)).bot
    assert saved.state is S.AWAITING_RANGE
    assert saved.definition.config["trigger_price"] == "125"
