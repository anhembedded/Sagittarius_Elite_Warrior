"""`EPIC-029E` — a bot that stops placing while the exchange is reachable takes its
ladder off it, and its exits stay armed (ADR D11, D13; PR 325 review).

`halt` and `fault` used to change only the state: the rest of the ladder kept
trading on the exchange, its fills owed counters nobody placed, and the stop
loss was watched only in RUNNING and PAUSED. Now every task that leaves the
bot HALTED or ERROR, other than a switch-off (when cancels are refused anyway
and the orders rest by design, D13), cancels every order carrying the bot's
tag; what it could not cancel is named beside the reason. In HALTED and ERROR
a tick through the stop loss or the take profit still runs Stop, selling the
base.
"""

from __future__ import annotations

from decimal import Decimal

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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    GridWorld,
    grid_world,
)

S = BotLifecycleState


def _running() -> GridWorld:
    world = grid_world()
    world.executor.start()
    world.book.requests.clear()
    return world


def test_a_rejection_halts_and_takes_the_ladder_off_the_exchange() -> None:
    world = _running()
    oid = world.open_ids_by_price()[Decimal(140)]
    world.book.open.pop(oid)

    world.executor.on_end(BotOrderEnd(oid, rejection="PERCENT_PRICE_BY_SIDE"))

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.ORDER_REJECTED
    assert world.book.open == {}
    assert world.runtime().open_orders == ()


def test_a_counter_that_faulted_takes_the_ladder_off_the_exchange() -> None:
    world = _running()
    world.book.raise_next = [ConnectionError("read timed out")]

    world.fill(Decimal(110), "2.272")

    assert world.state() is S.ERROR
    assert world.runtime().reason is GridReason.ORDER_FAILED
    assert world.book.open == {}


def test_a_switch_off_leaves_the_orders_resting_as_designed() -> None:
    world = _running()
    resting = set(world.book.open)

    world.executor.on_switch(False, TradingSwitchCause.DISABLED)

    assert world.state() is S.HALTED
    assert set(world.book.open) == resting
    assert world.book.cancels == []


def test_a_cancel_the_halt_could_not_make_is_named_beside_the_reason() -> None:
    world = _running()
    oid = world.open_ids_by_price()[Decimal(140)]
    world.book.open.pop(oid)
    world.book.cancel_raises = [ConnectionError("read timed out")]

    world.executor.on_end(BotOrderEnd(oid, rejection="insufficient balance"))

    runtime = world.runtime()
    assert world.state() is S.HALTED
    assert runtime.reason is GridReason.ORDER_REJECTED
    assert "insufficient balance" in runtime.reason_detail
    assert "may still rest" in runtime.reason_detail


def test_a_halted_bot_still_runs_its_stop_loss() -> None:
    world = _running()
    oid = world.open_ids_by_price()[Decimal(140)]
    world.book.open.pop(oid)
    world.executor.on_end(BotOrderEnd(oid, rejection="insufficient balance"))
    world.derive("4.126")

    world.executor.on_tick(Decimal(89))

    assert world.state() is S.STOPPED
    assert world.runtime().reason is GridReason.STOP_LOSS
    sells = [r for r in world.book.requests if r.order_type is OrderType.MARKET]
    assert sum(r.quantity for r in sells) == Decimal("4.126")


def test_a_faulted_bot_still_runs_its_take_profit() -> None:
    world = _running()
    world.book.raise_next = [ConnectionError("read timed out")]
    world.fill(Decimal(110), "2.272")
    assert world.state() is S.ERROR

    world.executor.on_tick(Decimal(150))

    assert world.state() is S.STOPPED
    assert world.runtime().reason is GridReason.TAKE_PROFIT
