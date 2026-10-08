"""`EPIC-035L` (audit H7) — a running bot reports the price leaving its range.

The fact is a typed `BotRangeChangedEvent` on the bus, published from the same
`PriceTick` the stop loss reads (`BUG-191`); no second price path. It is published
once when the price leaves the range and once when it returns, so the alert
`EPIC-036B` builds on it is once per exit and re-armed on return. The bot's own
behaviour does not change (D2): no automatic exit, no pause.

The world's range is 100–140, its stop loss `price:90`, its take profit `price:150`.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_price_tick import (
    PriceTick,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_range_changed_event import (
    BotRangeChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.range_position import (
    RangePosition,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    BOT,
    SYMBOL,
    GridWorld,
    grid_world,
)

S = BotLifecycleState
P = RangePosition


def _running() -> GridWorld:
    world = grid_world()
    world.executor.start()
    assert world.state() is S.RUNNING
    return world


def _heard(world: GridWorld) -> list[tuple[P, Decimal]]:
    return [
        (event.position, event.price)
        for event in world.events.events
        if isinstance(event, BotRangeChangedEvent)
    ]


def _tick(world: GridWorld, price: str) -> None:
    world.executor.facts.on_tick(PriceTick.at(Decimal(price)))


def test_a_price_below_the_lower_bound_is_reported_once() -> None:
    world = _running()
    orders = dict(world.book.open)

    _tick(world, "99")
    _tick(world, "98")

    assert _heard(world) == [(P.BELOW, Decimal(99))]
    event = world.events.events[-1]
    assert isinstance(event, BotRangeChangedEvent)
    assert (event.bot_id, event.symbol) == (BOT, SYMBOL)
    assert (event.lower, event.upper) == (100, 140)
    assert world.state() is S.RUNNING
    assert world.book.open == orders


def test_a_price_above_the_upper_bound_is_reported() -> None:
    world = _running()

    _tick(world, "141")

    assert _heard(world) == [(P.ABOVE, Decimal(141))]
    assert world.state() is S.RUNNING


def test_a_return_is_reported_and_re_arms_the_next_exit() -> None:
    world = _running()

    _tick(world, "99")
    _tick(world, "110")
    _tick(world, "99")

    assert _heard(world) == [
        (P.BELOW, Decimal(99)),
        (P.INSIDE, Decimal(110)),
        (P.BELOW, Decimal(99)),
    ]


def test_leaving_by_one_bound_and_arriving_at_the_other_is_a_new_exit() -> None:
    world = _running()

    _tick(world, "99")
    _tick(world, "141")

    assert [position for position, _ in _heard(world)] == [P.BELOW, P.ABOVE]


@pytest.mark.parametrize("price", ["100", "140", "120"])
def test_a_price_on_a_bound_or_inside_is_not_an_exit(price: str) -> None:
    world = _running()

    _tick(world, price)

    assert _heard(world) == []


def test_a_wick_outside_with_the_close_inside_is_not_a_range_exit() -> None:
    """The stop loss reads the traded range (`BUG-191`); the range alert reads
    where the price is, or one pierced bound would alert twice a second."""
    world = _running()

    world.executor.facts.on_tick(
        PriceTick(Decimal(110), Decimal(95), Decimal(145), None)
    )

    assert _heard(world) == []


def test_a_bot_at_rest_reports_nothing() -> None:
    world = grid_world(state=S.STOPPED)

    _tick(world, "99")

    assert _heard(world) == []


def test_a_stop_loss_and_a_range_exit_on_one_tick_are_both_acted_on() -> None:
    world = _running()

    _tick(world, "89")

    assert _heard(world) == [(P.BELOW, Decimal(89))]
    assert world.state() is S.STOPPED
