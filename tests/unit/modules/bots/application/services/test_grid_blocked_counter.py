"""`BUG-225` - a counter order that finds its level occupied asks the exchange before it halts.

The lower BUY (100) fills first and its counter wants the level of the BUY at 110. What the
exchange says of the 110 order decides: filled, the counter waits for that order's own fill;
cancelled, the level is freed; still open, it is a real duplicate and the bot halts as before.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_order_filled_event import (
    BotOrderFilledEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    OrderStatus,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.gap_world import (
    running,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    GridWorld,
)

S = BotLifecycleState
D = Decimal


def _exchange_says(world: GridWorld, price: Decimal, status: OrderStatus) -> None:
    cid = world.open_ids_by_price()[price]
    world.book.open[cid] = replace(world.book.open[cid], status=status)


def _fill_whole(world: GridWorld, price: Decimal) -> None:
    quantity = world.book.open[world.open_ids_by_price()[price]].quantity
    world.fill(price, str(quantity))


def _resting_sells(world: GridWorld) -> set[Decimal]:
    return {
        order.price
        for order in world.book.open.values()
        if order.side is OrderSide.SELL and order.price is not None
    }


def test_an_order_still_open_in_the_way_is_a_real_duplicate_and_halts() -> None:
    world = running()

    _fill_whole(world, D(100))

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.DUPLICATE_LEVEL_ORDER
    assert "L1 already holds an order; the counter of L0 cannot go there" in (
        world.runtime().reason_detail or ""
    )


def test_an_order_the_exchange_cancelled_frees_the_level_for_the_counter() -> None:
    world = running()
    _exchange_says(world, D(110), OrderStatus.CANCELED)

    _fill_whole(world, D(100))

    assert world.state() is S.RUNNING
    assert D(110) in _resting_sells(world)


def test_a_filled_order_in_the_way_parks_the_counter_until_its_own_fill() -> None:
    world = running()
    _exchange_says(world, D(110), OrderStatus.FILLED)

    _fill_whole(world, D(100))

    assert world.state() is S.RUNNING
    assert D(110) not in _resting_sells(world), "nothing is placed before the 110 fill"

    _fill_whole(world, D(110))

    assert world.state() is S.RUNNING
    assert {D(110), D(120)} <= _resting_sells(world)
    assert world.runtime().reason is None


def _announced_prices(world: GridWorld) -> list[Decimal]:
    return [
        event.price
        for event in world.events.events
        if isinstance(event, BotOrderFilledEvent)
    ]


def test_a_parked_fill_is_announced_when_it_is_applied_not_when_it_is_parked() -> None:
    """`BOT-189`: the fill whose counter waits is a real fill and is told once, with its own."""
    world = running()
    _exchange_says(world, D(110), OrderStatus.FILLED)

    _fill_whole(world, D(100))
    assert _announced_prices(world) == [], "parked: nothing is applied yet"

    _fill_whole(world, D(110))

    assert sorted(_announced_prices(world)) == [D(100), D(110)]


def test_a_real_fill_whose_counter_halts_the_bot_is_still_announced_once() -> None:
    world = running()

    _fill_whole(world, D(100))

    assert world.state() is S.HALTED
    assert _announced_prices(world) == [D(100)]
