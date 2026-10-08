"""`EPIC-035B` (audit H2) — a running Grid catches up after a stream gap.

Binance cuts every websocket at 24 h, so a gap is routine, and the stream does
not replay what happened in it. After every reconnect, and periodically, a
RUNNING or PAUSED bot is reconciled against the exchange with the missed-fill
logic `GridReconciler` already has for a restart: a fill missed in the gap
places its counter order, and a reconcile with nothing missed places nothing.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_order_events import (
    BotOrderFill,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRefusal,
    OwnerBudgetRegistrationResult,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.gap_world import (
    ManualWorkQueue,
    filled_in_the_gap,
    running,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    SYMBOL,
    GridWorld,
    grid_world,
)

S = BotLifecycleState
_AT = datetime(2026, 10, 4, 9, tzinfo=UTC)


def _bought_in_the_gap(world: GridWorld, quantity: str) -> None:
    derived = world.runtime().inventory + Decimal(quantity)
    world.derive(str(derived))
    world.hold(str(derived))


def test_a_fill_missed_in_the_gap_places_its_counter_order() -> None:
    """Red before: no catch-up path existed, so the BUY at 110 filled while the
    stream was down and its SELL at 120 was never placed."""
    world = running()
    before = world.runtime().inventory
    filled_in_the_gap(world, Decimal(110), "2.272")
    _bought_in_the_gap(world, "2.272")

    world.executor.reconcile_after_gap()

    assert world.state() is S.RUNNING
    assert [(r.side, r.reference_price) for r in world.book.requests[-1:]] == [
        (OrderSide.SELL, Decimal(120))
    ]
    assert world.runtime().inventory == before + Decimal("2.272")
    assert Decimal(120) in world.open_ids_by_price()


def test_a_reconcile_with_nothing_missed_places_nothing() -> None:
    world = running()
    requests = len(world.book.requests)
    runtime = world.runtime()

    world.executor.reconcile_after_gap()
    world.executor.reconcile_after_gap()

    assert world.state() is S.RUNNING
    assert len(world.book.requests) == requests
    assert world.runtime() == runtime


def test_a_gap_reconcile_run_twice_places_the_counter_once() -> None:
    """Idempotent: the second run finds the counter resting and the fill
    already counted."""
    world = running()
    filled_in_the_gap(world, Decimal(110), "2.272")
    _bought_in_the_gap(world, "2.272")

    world.executor.reconcile_after_gap()
    placed = len(world.book.requests)
    world.executor.reconcile_after_gap()

    assert len(world.book.requests) == placed


def test_a_paused_bot_counts_the_gap_fill_but_holds_its_counter() -> None:
    world = running()
    world.executor.pause()
    assert world.state() is S.PAUSED
    requests = len(world.book.requests)
    filled_in_the_gap(world, Decimal(110), "2.272")
    _bought_in_the_gap(world, "2.272")

    world.executor.reconcile_after_gap()

    assert world.state() is S.PAUSED
    assert len(world.book.requests) == requests, "nothing placed while paused"
    assert world.runtime().held, "the counter is owed, held for the resume"


def test_an_order_sent_but_never_saved_is_adopted_not_placed_twice() -> None:
    world = running()
    filled_in_the_gap(world, Decimal(110), "2.272")
    _bought_in_the_gap(world, "2.272")
    resting = next(iter(world.book.open.values()))
    unsaved = Order(
        resting.client_order_id.replace(resting.client_order_id[-8:], "0badc0de"),
        SYMBOL,
        OrderSide.SELL,
        OrderType.LIMIT,
        Decimal("2.272"),
        price=Decimal(120),
    )
    world.book.open[unsaved.client_order_id] = unsaved
    requests = len(world.book.requests)

    world.executor.reconcile_after_gap()

    assert world.state() is S.RUNNING
    assert len(world.book.requests) == requests
    level = next(lv for lv in world.runtime().levels if lv.price == Decimal(120))
    assert level.order is not None
    assert level.order.client_order_id == unsaved.client_order_id


def test_a_saved_inventory_unlike_the_derived_one_halts_and_parks_the_ladder() -> None:
    world = running()
    world.derive("99")
    world.hold("99")

    world.executor.reconcile_after_gap()

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.INVENTORY_MISMATCH
    assert world.book.open == {}, "a halt takes the ladder off (GridTaskGuard)"


def test_order_history_that_does_not_answer_is_a_wait_not_a_fault() -> None:
    world = running()
    filled_in_the_gap(world, Decimal(110), "2.272")
    world.activity.history_unavailable = True
    requests = len(world.book.requests)
    runtime = world.runtime()

    world.executor.reconcile_after_gap()

    assert world.state() is S.RUNNING
    assert len(world.book.requests) == requests
    assert world.runtime() == runtime, "the next periodic run retries"


def test_a_refused_budget_registration_leaves_a_running_bot_alone() -> None:
    world = running()
    world.session.register_owner_budget_answers(
        OwnerBudgetRegistrationResult(OwnerBudgetRefusal.INVENTORY_UNAVAILABLE)
    )
    runtime = world.runtime()

    world.executor.reconcile_after_gap()

    assert world.state() is S.RUNNING
    assert world.runtime() == runtime


@pytest.mark.parametrize("state", [S.HALTED, S.STOPPING, S.ERROR, S.STOPPED, S.DRAFT])
def test_only_a_running_or_paused_bot_reconciles_after_a_gap(
    state: BotLifecycleState,
) -> None:
    """Red before: the method did not exist. A HALTED bot in particular is
    never touched, so a stream that comes back cannot resume it."""
    world = grid_world(state=state)
    requests = len(world.book.requests)

    world.executor.reconcile_after_gap()

    assert world.state() is state
    assert len(world.book.requests) == requests


def test_a_fill_that_arrives_while_the_reconcile_reads_does_not_halt_the_bot() -> None:
    """The race a worker queue makes real: a partial fill happens, the history
    the reconcile reads already holds it, and the stream's event for it sits in
    the queue *behind* the reconcile. The first run sees the exchange ahead of
    the ladder; a disagreement is confirmed by a second run, queued behind that
    event, before it halts anything. Red before: the first run halted."""
    queue = ManualWorkQueue()
    world = grid_world(queue=queue)
    world.executor.start()
    queue.run_all()
    assert world.state() is S.RUNNING
    before = world.runtime().inventory
    partial = Decimal("0.003")
    world.derive(str(before + partial))
    world.hold(str(before + partial))
    resting = world.book.open[world.open_ids_by_price()[Decimal(110)]]

    world.executor.reconcile_after_gap()
    world.executor.on_fill(
        BotOrderFill(
            resting.client_order_id,
            resting.side,
            Decimal(110),
            partial,
            Decimal(0),
            "USDT",
        )
    )
    queue.run_all()

    assert world.state() is S.RUNNING
    assert world.runtime().inventory == before + partial


def test_a_disagreement_that_the_second_run_still_finds_halts_the_bot() -> None:
    queue = ManualWorkQueue()
    world = grid_world(queue=queue)
    world.executor.start()
    queue.run_all()
    world.derive("99")
    world.hold("99")

    world.executor.reconcile_after_gap()
    queue.run_all()

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.INVENTORY_MISMATCH


def test_a_disagreement_that_cleared_is_forgotten_by_the_next_one() -> None:
    """One strike, then agreement, then a strike again is not two in a row."""
    queue = ManualWorkQueue()
    world = grid_world(queue=queue)
    world.executor.start()
    queue.run_all()
    inventory = world.runtime().inventory
    world.hold("99")

    world.derive("99")
    world.executor.reconcile_after_gap()
    queue.run_next()  # strike one: the confirming run is queued
    world.derive(str(inventory))  # the ladder caught up before it ran
    queue.run_all()
    assert world.state() is S.RUNNING

    world.derive("99")
    world.executor.reconcile_after_gap()
    queue.run_next()  # strike one again, not strike two

    assert world.state() is S.RUNNING
    world.derive(str(inventory))
    queue.run_all()
    assert world.state() is S.RUNNING


def _one_disagreement_pending(world: GridWorld, queue: ManualWorkQueue) -> None:
    """Strike one has happened and its confirming run is queued."""
    world.derive("99")
    world.hold("99")
    world.executor.reconcile_after_gap()
    queue.run_next()
    assert world.state() is S.RUNNING


def test_a_confirming_run_that_could_not_read_clears_the_strike() -> None:
    """Review of PR 431, finding 1. Strike one, then the confirming run waits
    (history did not answer), then a lone disagreement five minutes later: that
    is a first sighting again, not a second. Red before: it halted."""
    queue = ManualWorkQueue()
    world = grid_world(queue=queue)
    world.executor.start()
    queue.run_all()
    _one_disagreement_pending(world, queue)

    world.session.register_owner_budget_answers(
        OwnerBudgetRegistrationResult(OwnerBudgetRefusal.INVENTORY_UNAVAILABLE)
    )
    queue.run_next()  # the confirming run cannot read: no verdict
    world.derive("99")
    world.executor.reconcile_after_gap()  # the periodic run, a lone sighting
    queue.run_next()

    assert world.state() is S.RUNNING


def test_a_confirming_run_that_raised_clears_the_strike() -> None:
    queue = ManualWorkQueue()
    world = grid_world(queue=queue)
    world.executor.start()
    queue.run_all()
    _one_disagreement_pending(world, queue)

    real_open_orders = world.activity.open_orders

    def timing_out() -> tuple[Order, ...]:
        raise TimeoutError("openOrders timed out")

    world.activity.open_orders = timing_out  # type: ignore[method-assign]
    queue.run_next()
    world.activity.open_orders = real_open_orders  # type: ignore[method-assign]
    world.executor.reconcile_after_gap()
    queue.run_next()

    assert world.state() is S.RUNNING


def test_a_fill_between_the_history_read_and_the_open_orders_read_is_not_lost() -> None:
    """Review of PR 431, finding 3. A registration reads history fresh, then
    the open orders are read, then the order's record comes from the history
    just read (a cache serves it). A saved order that fills in between is gone
    from the open orders while that history shows nothing executed: it was
    dropped with no fill and no counter order. Open orders are read first, so
    an order that fills later is still open in them and waits for the next run.
    Red before: the BUY at 110 was dropped and its SELL never placed."""
    world = running()
    quantity = Decimal("2.272")
    bought = world.runtime().inventory + quantity
    world.hold(str(bought))
    registrations = 0
    registered = world.session.register_owner_budget

    def registering(registration):
        nonlocal registrations
        registrations += 1
        result = registered(registration)
        # What the history reader remembers is what it read just now ...
        world.activity.remembered_orders = tuple(world.activity.orders)
        if registrations == 1:
            # ... and only then does the order fill.
            filled_in_the_gap(world, Decimal(110), str(quantity))
            world.derive(str(bought))
        else:
            world.activity.remembered_orders = tuple(world.activity.orders)
        return result

    world.session.register_owner_budget = registering  # type: ignore[method-assign]
    world.derive(str(world.runtime().inventory))

    world.executor.reconcile_after_gap()  # the fill lands during this run
    world.executor.reconcile_after_gap()  # the next run finds it

    assert world.state() is S.RUNNING
    assert Decimal(120) in world.open_ids_by_price(), "the counter order was placed"
    assert world.runtime().inventory == bought
