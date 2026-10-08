"""`BUG-187`, `BUG-188` — a gap reconcile reads every saved order, resting or not.

An order that ended without filling while the stream was down is laid again
once, as the stream's end event would have done; a partial fill of an order
that stays open is counted, so the inventory check agrees and the bot stays
RUNNING. Split from `test_grid_reconciler_gap.py` (400-line ceiling).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trade_record import (
    TradeRecord,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.gap_world import (
    cancelled_in_the_gap,
    partly_filled_in_the_gap,
    running,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    SYMBOL,
    GridWorld,
)

S = BotLifecycleState
_AT = datetime(2026, 10, 4, 9, tzinfo=UTC)


def _bought_in_the_gap(world: GridWorld, quantity: str) -> None:
    derived = world.runtime().inventory + Decimal(quantity)
    world.derive(str(derived))
    world.hold(str(derived))


def test_an_order_cancelled_in_the_gap_is_laid_again() -> None:
    """`BUG-187`. The BUY at 110 was cancelled on the exchange's website while
    the stream was down. Red before: the reconcile emptied the level with
    `drop_order` and nothing laid it again, where the stream's own end event
    would have re-placed it once."""
    world = running()
    cancelled_in_the_gap(world, Decimal(110))
    requests = len(world.book.requests)

    world.executor.reconcile_after_gap()

    assert world.state() is S.RUNNING
    assert [(r.side, r.reference_price) for r in world.book.requests[requests:]] == [
        (OrderSide.BUY, Decimal(110))
    ]
    assert Decimal(110) in world.open_ids_by_price()


def test_a_cancel_found_by_two_reconciles_is_laid_once() -> None:
    world = running()
    cancelled_in_the_gap(world, Decimal(110))

    world.executor.reconcile_after_gap()
    placed = len(world.book.requests)
    world.executor.reconcile_after_gap()

    assert len(world.book.requests) == placed


def test_a_paused_bot_holds_the_laying_again_of_a_cancelled_order() -> None:
    world = running()
    world.executor.pause()
    requests = len(world.book.requests)
    cancelled_in_the_gap(world, Decimal(110))

    world.executor.reconcile_after_gap()

    assert world.state() is S.PAUSED
    assert len(world.book.requests) == requests, "nothing placed while paused"
    assert [h.level_index for h in world.runtime().held] == [1]


def test_an_order_cancelled_twice_within_a_minute_halts_the_bot() -> None:
    """The stream's own rule (`LEVEL_KEEPS_ENDING`) holds for a reconcile: a
    level whose order was cancelled again right after its re-placement is a
    fault, not a hole."""
    world = running()
    cancelled_in_the_gap(world, Decimal(110))
    world.executor.reconcile_after_gap()
    assert world.state() is S.RUNNING
    cancelled_in_the_gap(world, Decimal(110))

    world.executor.reconcile_after_gap()
    world.executor.reconcile_after_gap()

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.LEVEL_KEEPS_ENDING


def test_a_partial_fill_missed_in_the_gap_is_counted_and_the_order_stays_resting() -> (
    None
):
    """`BUG-188`. 0.003 BTC of the BUY at 110 filled while the stream was down
    and the order stays open. Red before: the open order was never re-read, so
    the inventory stayed short of the exchange's and both runs halted the bot
    with `INVENTORY_MISMATCH`."""
    world = running()
    before = world.runtime().inventory
    requests = len(world.book.requests)
    partly_filled_in_the_gap(world, Decimal(110), "0.003")
    _bought_in_the_gap(world, "0.003")

    world.executor.reconcile_after_gap()
    world.executor.reconcile_after_gap()

    assert world.state() is S.RUNNING
    assert world.runtime().inventory == before + Decimal("0.003")
    level = next(lv for lv in world.runtime().levels if lv.price == Decimal(110))
    assert level.order is not None
    assert level.order.executed == Decimal("0.003")
    assert len(world.book.requests) == requests, "its counter is owed on completion"
    assert Decimal(110) in world.open_ids_by_price()


def test_a_partial_fill_is_applied_once_however_often_the_reconcile_runs() -> None:
    world = running()
    partly_filled_in_the_gap(world, Decimal(110), "0.003")
    _bought_in_the_gap(world, "0.003")

    world.executor.reconcile_after_gap()
    after_one = world.runtime()
    world.executor.reconcile_after_gap()

    assert world.runtime() == after_one


def test_the_fee_a_missed_partial_fill_paid_is_counted_once() -> None:
    world = running()
    before = world.runtime().inventory
    partly_filled_in_the_gap(world, Decimal(110), "0.003")
    world.activity.trades.append(
        TradeRecord(
            symbol=SYMBOL,
            trade_id=90,
            order_id=9,
            side=OrderSide.BUY,
            price=Decimal(110),
            quantity=Decimal("0.003"),
            quote_quantity=Decimal("0.33"),
            fee=Decimal("0.000003"),
            fee_asset="BTC",
            time=_AT,
        )
    )
    _bought_in_the_gap(world, "0.002997")

    world.executor.reconcile_after_gap()
    world.executor.reconcile_after_gap()

    assert world.state() is S.RUNNING
    assert world.runtime().inventory == before + Decimal("0.002997")
