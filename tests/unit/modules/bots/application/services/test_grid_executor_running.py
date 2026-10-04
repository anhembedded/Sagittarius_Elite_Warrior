"""`EPIC-029E` — a running Grid's fills, ends, pause and switch (ADR D9–D11, §3.2).

Each test starts the bot against the simulated venue, then feeds it what the
user data stream would: a fill flips its level one away, a pause holds the
counter order until resume, an order that ends is re-placed once and the second
end within a minute halts, a rejection halts, and trading off halts without
another order.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_runtime_codec import (
    decode_runtime,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_order_events import (
    BotOrderEnd,
    BotOrderFill,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
    GridRuntime,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.trading_switch_changed_event import (
    TradingSwitchCause,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    BOT,
    GridWorld,
    grid_world,
    minutes,
)

S = BotLifecycleState


def _running() -> GridWorld:
    world = grid_world()
    world.executor.start()
    assert world.state() is S.RUNNING
    world.book.requests.clear()
    return world


def _runtime(world: GridWorld) -> GridRuntime:
    return decode_runtime(world.store.load(BotId(BOT)).runtime)


def test_a_full_buy_places_the_sell_one_level_up() -> None:
    world = _running()

    world.fill(Decimal(110), "2.272", fee="0.002", asset="BTC")

    assert [(r.side, r.reference_price, r.quantity) for r in world.book.requests] == [
        (OrderSide.SELL, Decimal(120), Decimal("2.270"))
    ]
    assert Decimal(120) in world.open_ids_by_price()


def test_a_fill_in_three_events_places_exactly_one_counter_order() -> None:
    world = _running()
    oid = world.open_ids_by_price()[Decimal(110)]
    for piece in ("1", "1", "0.272"):
        world.executor.on_fill(_fill(oid, OrderSide.BUY, Decimal(110), piece))

    assert len(world.book.requests) == 1


def test_profit_is_booked_once_when_the_counter_sell_fills() -> None:
    world = _running()
    world.fill(Decimal(110), "2.272")
    world.fill(Decimal(120), "2.272")

    runtime = _runtime(world)
    assert runtime.completed_cycles == 1
    assert runtime.realised_profit == Decimal("22.720")


def test_a_pause_holds_the_counter_order_and_resume_places_it() -> None:
    world = _running()
    world.executor.pause()
    assert world.state() is S.PAUSED

    world.fill(Decimal(110), "2.272")

    assert world.book.requests == []
    world.executor.resume()
    assert world.state() is S.RUNNING
    assert [(r.side, r.reference_price) for r in world.book.requests] == [
        (OrderSide.SELL, Decimal(120))
    ]


def test_two_fills_in_one_pause_never_release_a_crossing_pair() -> None:
    world = _running()
    world.executor.pause()

    world.fill(Decimal(110), "2.272")
    world.fill(Decimal(130), "2.063")

    assert world.state() is S.HALTED
    assert _runtime(world).reason is GridReason.DUPLICATE_LEVEL_ORDER
    world.executor.resume()
    at_120 = [r.side for r in world.book.requests if r.reference_price == Decimal(120)]
    assert len(at_120) <= 1


def test_an_order_is_never_sent_to_a_level_that_already_holds_one() -> None:
    """The executor checks the level before it submits: a release aimed at a
    level that holds an order halts with nothing sent, instead of sending it
    and failing the level transition afterwards."""
    world = _running()
    world.executor.pause()
    world.fill(Decimal(110), "2.272")
    paused = _runtime(world)
    resting = world.open_ids_by_price()[Decimal(130)]
    level = paused.level_of(resting)
    assert level is not None
    crowded = paused.with_level(
        replace(paused.levels[2], state=level.state, order=level.order)
    )
    world = grid_world(state=S.PAUSED, runtime=crowded)

    world.executor.resume()

    assert world.book.requests == []
    assert world.state() is S.HALTED
    assert _runtime(world).reason is GridReason.DUPLICATE_LEVEL_ORDER


def test_a_late_duplicate_fill_of_a_settled_level_changes_nothing() -> None:
    """A fill for an id the ladder no longer holds is a market fill only if
    the bot sent that id as a market order or took it off the ladder; a late
    duplicate of a settled level's fill, or an earlier run's order, is not."""
    world = _running()
    oid = world.open_ids_by_price()[Decimal(110)]
    world.fill(Decimal(110), "2.272")
    held = _runtime(world).inventory

    world.executor.on_fill(
        BotOrderFill(oid, OrderSide.BUY, Decimal(110), Decimal("2.272"), None, None)
    )

    assert _runtime(world).inventory == held


def test_an_opening_market_slice_still_moves_the_inventory() -> None:
    world = grid_world()
    world.executor.start()
    slice_id = world.book.submitted[0]

    world.executor.on_fill(
        BotOrderFill(
            slice_id, OrderSide.BUY, Decimal(121), Decimal("2.066"), None, None
        )
    )

    assert _runtime(world).inventory == Decimal("2.066")


def test_an_order_cancelled_from_outside_is_placed_again_once() -> None:
    world = _running()
    oid = world.open_ids_by_price()[Decimal(100)]
    world.book.open.pop(oid)

    world.executor.on_end(BotOrderEnd(oid))

    assert [(r.side, r.reference_price) for r in world.book.requests] == [
        (OrderSide.BUY, Decimal(100))
    ]
    assert world.state() is S.RUNNING


def test_a_second_end_at_one_level_within_a_minute_halts() -> None:
    world = _running()
    first = world.open_ids_by_price()[Decimal(100)]
    world.book.open.pop(first)
    world.executor.on_end(BotOrderEnd(first))
    world.clock.advance(minutes(1) / 2)
    second = world.open_ids_by_price()[Decimal(100)]
    world.book.open.pop(second)

    world.executor.on_end(BotOrderEnd(second))

    assert world.state() is S.HALTED
    assert _runtime(world).reason is GridReason.LEVEL_KEEPS_ENDING


def test_a_rejection_halts_with_the_exchanges_reason() -> None:
    world = _running()
    oid = world.open_ids_by_price()[Decimal(140)]

    world.executor.on_end(BotOrderEnd(oid, rejection="insufficient balance"))

    assert world.state() is S.HALTED
    runtime = _runtime(world)
    assert runtime.reason is GridReason.ORDER_REJECTED
    assert "insufficient balance" in runtime.reason_detail


def test_a_disable_halts_and_says_the_orders_still_rest() -> None:
    world = _running()

    world.executor.on_switch(False, TradingSwitchCause.DISABLED)

    assert world.state() is S.HALTED
    assert world.book.requests == []
    runtime = _runtime(world)
    assert runtime.reason is GridReason.SWITCH_OFF
    assert "still on the exchange" in runtime.reason_detail


def test_an_emergency_stop_halts_and_a_later_fill_places_nothing() -> None:
    world = _running()

    world.executor.on_switch(False, TradingSwitchCause.EMERGENCY_STOP)
    world.fill(Decimal(110), "2.272")

    assert world.state() is S.HALTED
    assert world.book.requests == []
    assert _runtime(world).inventory > 0


def test_a_tick_through_the_stop_loss_runs_stop_selling_the_base() -> None:
    world = _running()

    world.executor.on_tick(Decimal(89))

    assert world.state() is S.STOPPED
    assert world.book.open == {}
    runtime = _runtime(world)
    assert runtime.reason is GridReason.STOP_LOSS
    assert runtime.sell_base_on_stop


def test_a_tick_inside_the_exits_changes_nothing() -> None:
    world = _running()

    world.executor.on_tick(Decimal(125))

    assert world.state() is S.RUNNING
    assert world.book.requests == []


def _fill(oid: str, side: OrderSide, price: Decimal, quantity: str) -> BotOrderFill:
    return BotOrderFill(oid, side, price, Decimal(quantity))
