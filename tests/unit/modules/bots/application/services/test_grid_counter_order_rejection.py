"""`EPIC-035T` — a counter order the exchange rejects does not kill the grid.

A counter order is one rung's worth of the ladder. When the exchange (or trading,
before the request) refuses it because of its own numbers — a quantity, a price
band, a minimum notional, a plain `-2010` — the rung stays EMPTY with a named
reason and the rest of the ladder goes on trading. The same rung refused twice
within a minute is the existing level rule: the bot halts. A refusal that is about
the bot or the venue, not the order (a limit, a lease, a switch), still halts.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_level_fsm_matrix import (
    LevelState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderNotionalRejection,
    ExecuteOrderPriceRejection,
    ExecuteOrderSafetyGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_rejection_reason import (
    OrderRejectedByExchangeError,
    OrderRejectionReason,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    GridWorld,
    grid_world,
    minutes,
)

S = BotLifecycleState
#: The rung a full BUY at L1 (110) owes a SELL at.
COUNTER_LEVEL = 2


def _running() -> GridWorld:
    world = grid_world()
    world.executor.start()
    assert world.state() is S.RUNNING
    world.book.requests.clear()
    return world


def _rejected(reason: OrderRejectionReason) -> OrderRejectedByExchangeError:
    return OrderRejectedByExchangeError(reason, f"{reason.value}: the exchange's words")


def _fill_l1(world: GridWorld) -> None:
    world.fill(Decimal(110), "2.272")


def test_a_rejected_counter_order_leaves_the_level_empty_and_the_bot_running() -> None:
    world = _running()
    resting = set(world.book.open)
    world.book.raise_next.append(_rejected(OrderRejectionReason.LOT_SIZE))

    _fill_l1(world)

    assert world.state() is S.RUNNING
    level = world.runtime().levels[COUNTER_LEVEL]
    assert level.state is LevelState.EMPTY and level.order is None
    assert world.book.cancels == [], "the rest of the ladder is not taken off"
    assert len(world.book.open) == len(resting) - 1


def test_the_rejection_is_named_with_the_rung_and_the_exchanges_words() -> None:
    world = _running()
    world.book.raise_next.append(_rejected(OrderRejectionReason.PRICE_FILTER))

    _fill_l1(world)

    runtime = world.runtime()
    assert runtime.reason is GridReason.COUNTER_ORDER_REJECTED
    assert f"L{COUNTER_LEVEL} SELL" in runtime.reason_detail
    assert "the exchange's words" in runtime.reason_detail


@pytest.mark.parametrize(
    "reason",
    [
        OrderRejectionReason.LOT_SIZE,
        OrderRejectionReason.MIN_NOTIONAL,
        OrderRejectionReason.PRICE_FILTER,
        OrderRejectionReason.NEW_ORDER_REJECTED,
    ],
)
def test_an_order_content_rejection_by_the_exchange_keeps_the_bot_running(
    reason: OrderRejectionReason,
) -> None:
    world = _running()
    world.book.raise_next.append(_rejected(reason))

    _fill_l1(world)

    assert world.state() is S.RUNNING
    assert world.runtime().reason is GridReason.COUNTER_ORDER_REJECTED


@pytest.mark.parametrize(
    "gate",
    [
        ExecuteOrderPriceRejection.OUTSIDE_PRICE_BAND,
        ExecuteOrderNotionalRejection.MIN_NOTIONAL,
    ],
)
def test_a_counter_order_trading_refuses_on_a_filter_keeps_the_bot_running(
    gate: object,
) -> None:
    """Trading checks the percent-price band and the minimum notional before it
    sends (`BUG-147`, `BUG-090`): the counter order is validated against the
    exchange filters already; what was missing was the bot surviving the answer."""
    world = _running()
    world.book.refuse_next.append(gate)  # type: ignore[arg-type]

    _fill_l1(world)

    assert world.state() is S.RUNNING
    assert world.runtime().reason is GridReason.COUNTER_ORDER_REJECTED
    assert world.runtime().levels[COUNTER_LEVEL].state is LevelState.EMPTY


def test_a_refusal_about_the_bot_not_the_order_still_halts() -> None:
    world = _running()
    world.book.refuse_next.append(ExecuteOrderSafetyGate.SYMBOL_LEASED)

    _fill_l1(world)

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.ORDER_REFUSED


def test_an_unnamed_exchange_rejection_is_still_a_fault() -> None:
    world = _running()
    world.book.raise_next.append(_rejected(OrderRejectionReason.UNKNOWN))

    _fill_l1(world)

    assert world.state() is S.ERROR


def test_the_same_rung_refused_twice_within_a_minute_halts() -> None:
    world = _running()
    world.book.raise_next.append(_rejected(OrderRejectionReason.LOT_SIZE))
    _fill_l1(world)
    assert world.state() is S.RUNNING
    world.clock.advance(minutes(1) / 2)
    world.book.raise_next.append(_rejected(OrderRejectionReason.LOT_SIZE))

    world.fill(Decimal(130), "2.066")

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.LEVEL_KEEPS_ENDING
    assert f"L{COUNTER_LEVEL}" in world.runtime().reason_detail


def test_the_same_rung_refused_again_after_a_minute_keeps_the_bot_running() -> None:
    world = _running()
    world.book.raise_next.append(_rejected(OrderRejectionReason.LOT_SIZE))
    _fill_l1(world)
    world.clock.advance(minutes(2))
    world.book.raise_next.append(_rejected(OrderRejectionReason.LOT_SIZE))

    world.fill(Decimal(130), "2.066")

    assert world.state() is S.RUNNING
    assert world.runtime().reason is GridReason.COUNTER_ORDER_REJECTED


def test_a_rejection_while_the_ladder_is_first_laid_is_a_refused_start_not_a_fault() -> (
    None
):
    world = grid_world()
    world.book.raise_next.append(_rejected(OrderRejectionReason.LOT_SIZE))

    world.executor.start()

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.START_REFUSED


def test_a_rejected_counter_order_survives_a_save_and_a_restart() -> None:
    world = _running()
    world.book.raise_next.append(_rejected(OrderRejectionReason.MIN_NOTIONAL))
    _fill_l1(world)

    saved = world.runtime()

    assert saved.reason is GridReason.COUNTER_ORDER_REJECTED
    assert saved.levels[COUNTER_LEVEL].ended_at, (
        "the rung remembers when it was refused"
    )
