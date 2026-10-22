"""`BUG-266` - a counter order's pairing is on record before the order is sent.

@details The pairing of a SELL counter (the BUY it completes) lived only in memory between the
send and the save of the placement. A request that raised while the order was live, or a death
in that gap, left a live SELL the restart's reconcile adopted with no pairing: its fill booked
into the inventory and closed no cycle, so Cycles and Grid profit came out short while Total PnL
did not move (the owner's `6tszoz` run: 20 cycles where 21 were expected).
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_reactions import (
    LevelFill,
    adopted,
    on_fill,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    LevelOrder,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_rejection_reason import (
    OrderRejectedByExchangeError,
    OrderRejectionReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    GridWorld,
    grid_world,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.grid_runtime_builders import (
    STEP,
)

S = BotLifecycleState
D = Decimal
#: The rung a full BUY at L1 (110) owes a SELL at.
COUNTER_LEVEL = 2
_ADOPTED = "SEW-a3f9c1-0000000099"


def _running() -> GridWorld:
    world = grid_world()
    world.executor.start()
    assert world.state() is S.RUNNING
    return world


def test_a_counter_order_that_faulted_while_live_is_adopted_with_its_pairing() -> None:
    world = _running()
    world.book.raise_next.append(ConnectionError("read timed out"))

    world.fill(D(110), "2.272")

    saved = world.runtime()
    (owed,) = saved.held
    assert owed.level_index == COUNTER_LEVEL and owed.side is OrderSide.SELL
    assert owed.paired_buy_price == D(110), "the intent kept the entry it completes"
    # The request raised after the order reached the exchange: the restart's reconcile finds it.
    adoptee = LevelOrder(_ADOPTED, OrderSide.SELL, D(120), owed.quantity)
    reconciled = adopted(saved, COUNTER_LEVEL, adoptee)
    done = on_fill(
        reconciled, LevelFill(_ADOPTED, D(120), owed.quantity), STEP, hold=False
    )
    assert done.runtime.completed_cycles == 1
    assert done.runtime.realised_profit > 0, "the cycle's profit is booked"


def test_an_accepted_counter_order_leaves_no_intent_behind_and_keeps_its_pairing() -> (
    None
):
    world = _running()

    world.fill(D(110), "2.272")

    saved = world.runtime()
    assert not saved.held, "the order is on the ladder, not owed"
    counter = saved.levels[COUNTER_LEVEL].order
    assert counter is not None and counter.paired_buy_price == D(110)


def test_a_counter_order_the_exchange_refused_for_its_numbers_leaves_no_intent() -> (
    None
):
    world = _running()
    world.book.raise_next.append(
        OrderRejectedByExchangeError(OrderRejectionReason.LOT_SIZE, "LOT_SIZE: no")
    )

    world.fill(D(110), "2.272")

    assert world.state() is S.RUNNING
    assert not world.runtime().held, "nothing reached the exchange, nothing is owed"
