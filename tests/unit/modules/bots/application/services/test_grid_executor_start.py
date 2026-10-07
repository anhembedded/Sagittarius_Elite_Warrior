"""`EPIC-029E` — a Grid's start, against a simulated Spot venue (ADR §3.1, §3.4, D9).

The opening buy goes in slices under the cap; the ladder follows outward from
the price with the nearest level empty; the bot is RUNNING only once every
other level rests. A refusal cancels what was placed and halts; trading off
halts, never ERROR; a request that raised is a fault.
"""

from __future__ import annotations

import threading
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.adapters.thread_bot_work_queue import (
    ThreadBotWorkQueue,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_runtime_codec import (
    decode_runtime,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_level_fsm_matrix import (
    LevelState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    tag_of,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderSafetyGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_outcome_unknown import (
    OrderOutcomeUnknownError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trading_limits import (
    TradingLimitViolation,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    BOT,
    LAST_PRICE,
    grid_world,
)

S = BotLifecycleState


def test_the_opening_buy_goes_in_slices_under_the_cap_then_the_ladder_outward() -> None:
    world = grid_world()

    world.executor.start()

    requests = world.book.requests
    market = [r for r in requests if r.order_type is OrderType.MARKET]
    assert [r.quote_quantity for r in market] == [Decimal("249.986")] * 2
    assert all(r.side is OrderSide.BUY for r in market)
    ladder = [(r.side, r.reference_price) for r in requests[len(market) :]]
    assert ladder == [
        (OrderSide.SELL, Decimal(130)),
        (OrderSide.BUY, Decimal(110)),
        (OrderSide.SELL, Decimal(140)),
        (OrderSide.BUY, Decimal(100)),
    ]
    assert world.state() is S.RUNNING


def test_every_order_carries_the_bots_owner_and_tag_and_waits_its_turn() -> None:
    world = grid_world()

    world.executor.start()

    assert {r.owner_id for r in world.book.requests} == {world.owner}
    assert {r.client_order_tag for r in world.book.requests} == {BOT}
    assert {tag_of(oid) for oid in world.book.open} == {BOT}
    assert world.pacer.turns == len(world.book.requests)


def test_the_level_nearest_the_price_stays_empty_and_the_rest_rest() -> None:
    world = grid_world()

    world.executor.start()

    runtime = decode_runtime(world.store.load(BotId(BOT)).runtime)
    states = {level.price: level.state for level in runtime.levels}
    assert states[Decimal(120)] is LevelState.EMPTY
    assert {
        states[p] for p in (Decimal(100), Decimal(110), Decimal(130), Decimal(140))
    } == {LevelState.RESTING}
    assert {o.client_order_id for o in runtime.open_orders} == set(world.book.open)


def test_a_refused_ladder_order_cancels_what_was_placed_and_halts() -> None:
    world = grid_world()
    world.book.refuse_next = [
        None,
        None,
        None,
        TradingLimitViolation.OWNER_BUDGET_EXPOSURE,
    ]

    world.executor.start()

    assert world.state() is S.HALTED
    assert world.book.open == {}
    runtime = decode_runtime(world.store.load(BotId(BOT)).runtime)
    assert runtime.reason is GridReason.START_REFUSED
    assert "owner_budget_exposure" in runtime.reason_detail


def test_a_refused_opening_slice_halts_before_any_ladder_order() -> None:
    world = grid_world()
    world.book.refuse_next = [None, TradingLimitViolation.OWNER_BUDGET_RATE]

    world.executor.start()

    assert world.state() is S.HALTED
    assert all(r.order_type is OrderType.MARKET for r in world.book.requests)
    runtime = decode_runtime(world.store.load(BotId(BOT)).runtime)
    assert runtime.reason is GridReason.START_REFUSED
    assert "opening buy slice 2" in runtime.reason_detail


def test_trading_switched_off_mid_start_halts_never_errors() -> None:
    """The Emergency Stop race (ADR D7, D9): a submit refused between the
    disable and its event is `switch_off`, so HALTED, not ERROR."""
    world = grid_world()
    world.book.refuse_next = [None, None, ExecuteOrderSafetyGate.TRADING_SWITCH_OFF]

    world.executor.start()

    assert world.state() is S.HALTED
    runtime = decode_runtime(world.store.load(BotId(BOT)).runtime)
    assert runtime.reason is GridReason.SWITCH_OFF


def test_a_connection_not_ready_is_also_switch_off() -> None:
    world = grid_world()
    world.book.refuse_next = [ExecuteOrderSafetyGate.CONNECTION_NOT_READY]

    world.executor.start()

    assert world.state() is S.HALTED
    runtime = decode_runtime(world.store.load(BotId(BOT)).runtime)
    assert runtime.reason is GridReason.SWITCH_OFF


def test_a_submit_that_raises_is_a_fault() -> None:
    world = grid_world()
    world.book.raise_next = [ConnectionError("reset by peer")]

    world.executor.start()

    assert world.state() is S.ERROR
    runtime = decode_runtime(world.store.load(BotId(BOT)).runtime)
    assert runtime.reason is GridReason.ORDER_FAILED
    assert "reset by peer" in runtime.reason_detail


def test_a_submit_whose_outcome_is_unknown_is_a_fault_saying_the_order_may_be_live() -> (
    None
):
    """`BUG-170`: the order may be on the exchange, so the bot never reads the
    failure as "not placed"; it stops in ERROR, whose exit derives the book again."""
    world = grid_world()
    world.book.raise_next = [
        OrderOutcomeUnknownError("BTCUSDT", "SEW-abc123-0123456789", "HTTP 502")
    ]

    world.executor.start()

    assert world.state() is S.ERROR
    runtime = decode_runtime(world.store.load(BotId(BOT)).runtime)
    assert runtime.reason is GridReason.ORDER_FAILED
    assert "may be live" in runtime.reason_detail
    assert "SEW-abc123-0123456789" in runtime.reason_detail


def test_a_start_outside_starting_does_nothing() -> None:
    world = grid_world(state=S.RUNNING)

    world.executor.start()

    assert world.book.requests == []


def test_every_submit_runs_on_the_bots_worker_never_on_the_callers_thread() -> None:
    queue = ThreadBotWorkQueue(f"bot-{BOT}")
    world = grid_world(queue=queue)

    world.executor.start()
    queue.close()

    assert world.book.threads
    assert set(world.book.threads) == {f"bot-{BOT}"}
    assert threading.current_thread().name not in world.book.threads


def test_the_reference_price_is_the_books_middle_until_a_tick_is_heard() -> None:
    world = grid_world()

    world.executor.start()

    assert {
        r.reference_price
        for r in world.book.requests
        if r.order_type is OrderType.MARKET
    } == {LAST_PRICE}


def test_each_sell_is_sized_net_of_the_fee_the_opening_paid_in_base() -> None:
    """The opening buys 4.132 BTC (2.066 a SELL level at 250 USDT and 121) and
    Spot takes the 0.1% taker fee from it, so 4.127868 arrives: each SELL asks
    for 2.063 (2.066 × 0.999, down to the 0.001 step), never the gross 2.066
    the last of which trading would refuse as more than the bot holds."""
    world = grid_world()

    world.executor.start()

    sells = [
        r.quantity
        for r in world.book.requests
        if r.order_type is OrderType.LIMIT and r.side is OrderSide.SELL
    ]
    assert sells == [Decimal("2.063"), Decimal("2.063")]
    assert sum(sells) <= Decimal("4.132") * Decimal("0.999")
