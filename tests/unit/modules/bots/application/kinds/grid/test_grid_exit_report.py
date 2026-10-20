"""`BOT-190` — an exit is told once, when the slice that leaves the run holding dust is booked.

A real Spot Grid executor over the simulated venue: a stop that closes at market sends its exit
slices, and the fills the test hands back are booked one by one on the executor's own facts. What
the bot published is read off the recording publisher.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from itertools import count

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_exit_report import (
    GridExitReport,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_order_events import (
    BotOrderFill,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_exit_closed_event import (
    BotExitClosedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    ExposureHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.trade_direction import (
    TradeDirection,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    ExposureKind,
    ExposureLimits,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    LAST_PRICE,
    GridWorld,
    grid_world,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.grid_runtime_builders import (
    started_ladder,
)

S = BotLifecycleState
HELD = Decimal(5)  # worth 605 at 121: three slices under the 300 cap
_TRADES = count(1)
_POSITION = ExposureLimits(frozenset(TradeDirection), 125, ExposureKind.POSITION)


def _stopping_world() -> GridWorld:
    runtime = replace(
        started_ladder(),
        inventory=HELD,
        cost=HELD * Decimal(100),
        mark_price=LAST_PRICE,
    )
    world = grid_world(state=S.RUNNING, runtime=runtime)
    world.derive(str(HELD), str(HELD * 100))
    world.executor.stop(ExposureHandling.CLOSE_AT_MARKET)
    assert world.state() is S.STOPPED
    return world


def _exit_slices(world: GridWorld) -> list[tuple[str, Decimal]]:
    sells = [r for r in world.book.requests if r.side is OrderSide.SELL]
    ids = world.book.submitted[-len(sells) :]
    return [(oid, r.quantity) for oid, r in zip(ids, sells, strict=True)]


def _fill(world: GridWorld, order_id: str, quantity: Decimal) -> None:
    world.executor.facts.on_fill(
        BotOrderFill(
            order_id,
            OrderSide.SELL,
            LAST_PRICE,
            quantity,
            Decimal(0),
            "USDT",
            next(_TRADES),
        )
    )


def _told(world: GridWorld) -> list[BotExitClosedEvent]:
    return [e for e in world.events.events if isinstance(e, BotExitClosedEvent)]


def test_the_exit_is_told_once_after_the_slice_that_leaves_dust_not_after_the_first() -> (
    None
):
    world = _stopping_world()
    slices = _exit_slices(world)
    assert len(slices) >= 2

    for order_id, quantity in slices[:-1]:
        _fill(world, order_id, quantity)
        assert _told(world) == []

    last_id, last_quantity = slices[-1]
    _fill(world, last_id, last_quantity)

    [event] = _told(world)
    assert (
        event.reason == GridReason.USER_STOP.value
    )  # the reason the executor's stop began with
    assert event.total_pnl == world.runtime().realised_total


def test_more_trades_of_the_last_slice_tell_nothing_again() -> None:
    world = _stopping_world()
    *earlier, (last_id, last_quantity) = _exit_slices(world)
    for order_id, quantity in earlier:
        _fill(world, order_id, quantity)
    half = last_quantity / 2

    _fill(world, last_id, half)
    _fill(world, last_id, half)
    _fill(world, last_id, Decimal(0))  # a further trade report of the same order

    assert len(_told(world)) == 1


def _flat_world(reason: GridReason | None = GridReason.STOP_LOSS) -> GridWorld:
    """A bot that holds nothing, with its exit slices to be named by the test."""
    runtime = replace(started_ladder(), mark_price=LAST_PRICE, reason=reason)
    return grid_world(state=S.STOPPED, runtime=runtime)


def _report(world: GridWorld, limits: ExposureLimits | None = None) -> GridExitReport:
    context = world.executor._context
    return GridExitReport(
        context if limits is None else replace(context, limits=limits)
    )


def test_the_guard_tells_an_exit_once_and_a_later_exit_of_the_run_again() -> None:
    world = _flat_world()
    report = _report(world)
    off_ladder = world.executor._context.off_ladder

    off_ladder.add_exit("first")
    report.after_exit_fill()
    report.after_exit_fill()  # a second trade of the same last slice
    assert len(_told(world)) == 1

    off_ladder.add_exit("second")  # a halt closed, then a stop loss closed again
    report.after_exit_fill()
    assert len(_told(world)) == 2


def test_nothing_is_told_before_an_exit_slice_was_sent() -> None:
    world = _flat_world()

    _report(world).after_exit_fill()

    assert _told(world) == []


def test_a_fill_before_any_stop_has_begun_tells_nothing_and_keeps_the_guard() -> None:
    """The exchange-side protective stop fills while the bot is RUNNING; the stop that follows
    gives the exit its reason."""
    world = _flat_world(reason=None)
    report = _report(world)
    world.executor._context.off_ladder.add_exit("protective")

    report.after_exit_fill()
    assert _told(world) == []

    world.executor._context.state.update(
        replace(
            world.executor._context.state.runtime,
            reason=GridReason.PROTECTIVE_STOP_TRIGGERED,
        )
    )
    report.after_exit_fill()
    [event] = _told(world)
    assert event.reason == GridReason.PROTECTIVE_STOP_TRIGGERED.value


def test_a_position_still_held_is_not_dust_so_nothing_is_told() -> None:
    world = _flat_world()
    context = world.executor._context
    context.state.update(replace(context.state.runtime, inventory=HELD))
    context.off_ladder.add_exit("slice")

    _report(world).after_exit_fill()

    assert _told(world) == []


def test_spot_keeps_a_base_below_the_minimum_notional_but_a_position_venue_closes_it() -> (
    None
):
    """0.02 at 121 is worth 2.42, under the 5 minimum, yet above one step: Spot's stop would keep
    it as dust; a reduce-only close ignores the minimum and would still sell it."""
    held = Decimal("0.02")
    spot, position = _flat_world(), _flat_world()
    for world in (spot, position):
        context = world.executor._context
        context.state.update(replace(context.state.runtime, inventory=held))
        context.off_ladder.add_exit("slice")

    _report(spot).after_exit_fill()
    _report(position, _POSITION).after_exit_fill()

    assert len(_told(spot)) == 1
    assert _told(position) == []
