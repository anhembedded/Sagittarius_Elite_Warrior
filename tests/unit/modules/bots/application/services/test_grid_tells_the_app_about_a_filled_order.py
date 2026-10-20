"""`BOT-189` — the executor publishes `BotOrderFilledEvent` once per order that filled whole.

The same executor over the simulated venue as `test_grid_executor_running.py`, and the same
`RecordingPublisher` that keeps what the bot announced. Partial fills and a trade the run already
counted announce nothing; the fill that closes a cycle carries the profit the run booked.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_order_events import (
    BotOrderFill,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_order_filled_event import (
    BotOrderFilledEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    BOT,
    GridWorld,
    grid_world,
)


def _running() -> GridWorld:
    world = grid_world()
    world.executor.start()
    return world


def _announced(world: GridWorld) -> list[BotOrderFilledEvent]:
    return [e for e in world.events.events if isinstance(e, BotOrderFilledEvent)]


def test_a_full_fill_is_announced_once_with_its_level_side_price_and_quantity() -> None:
    world = _running()
    order_id = world.open_ids_by_price()[Decimal(110)]

    world.fill(Decimal(110), "2.272")

    [event] = _announced(world)
    assert (event.bot_id, event.order_id) == (BOT, order_id)
    assert (event.side, event.price, event.quantity) == (
        "BUY",
        Decimal(110),
        Decimal("2.272"),
    )
    assert event.level == 1
    assert event.cycle_profit is None
    assert event.completed_cycles == 0


def test_the_opening_orders_of_the_start_are_not_ladder_fills() -> None:
    assert _announced(_running()) == []


def test_a_fill_in_three_events_is_announced_once_by_the_one_that_completes_it() -> (
    None
):
    world = _running()
    oid = world.open_ids_by_price()[Decimal(110)]
    for piece in ("1", "1"):
        world.executor.facts.on_fill(
            BotOrderFill(oid, OrderSide.BUY, Decimal(110), Decimal(piece))
        )
        assert _announced(world) == []

    world.executor.facts.on_fill(
        BotOrderFill(oid, OrderSide.BUY, Decimal(110), Decimal("0.272"))
    )

    assert len(_announced(world)) == 1


def test_the_counter_sell_that_closes_the_cycle_carries_the_profit_the_run_booked() -> (
    None
):
    world = _running()
    world.fill(Decimal(110), "2.272")
    world.fill(Decimal(120), "2.272")

    buy, sell = _announced(world)
    assert sell.side == "SELL"
    assert sell.cycle_profit == Decimal("22.720")
    assert sell.cycle_profit == world.runtime().realised_profit
    assert (sell.grid_profit, sell.completed_cycles) == (Decimal("22.720"), 1)
    assert buy.cycle_profit is None


def test_a_trade_the_run_already_counted_is_not_announced_again() -> None:
    world = _running()
    oid = world.open_ids_by_price()[Decimal(110)]
    fill = BotOrderFill(oid, OrderSide.BUY, Decimal(110), Decimal("2.272"), trade_id=77)

    world.executor.facts.on_fill(fill)
    world.executor.facts.on_fill(fill)

    assert len(_announced(world)) == 1
