"""`BUG-266` - a counter order's pairing is on record before the order is sent.

@details The pairing of a SELL counter (the BUY it completes) lived only in memory between the
send and the save of the placement. A death in that gap left a live SELL the restart's reconcile
adopted with no pairing: its fill booked
into the inventory and closed no cycle, so Cycles and Grid profit came out short while Total PnL
did not move (the owner's `6tszoz` run: 20 cycles where 21 were expected).
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_rejection_reason import (
    OrderRejectedByExchangeError,
    OrderRejectionReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    SYMBOL,
    GridWorld,
    grid_world,
)

S = BotLifecycleState
D = Decimal
#: The rung a full BUY at L1 (110) owes a SELL at.
COUNTER_LEVEL = 2
_ADOPTED = "SEW-a3f9c1-0000000099"


class _ProcessDied(BaseException):
    """The process ends here: nothing in the bot catches it, as nothing catches a SIGKILL."""


def _running() -> GridWorld:
    world = grid_world()
    world.executor.start()
    assert world.state() is S.RUNNING
    return world


def test_a_death_between_the_send_and_the_placement_save_leaves_the_pairing_to_the_restart() -> (
    None
):
    world = _running()
    world.book.raise_next.append(_ProcessDied())

    with pytest.raises(_ProcessDied):
        world.fill(D(110), "2.272")

    # What the file held when the process ended: the BUY booked, the SELL owed with its pairing.
    saved = world.runtime()
    (owed,) = saved.held
    assert owed.level_index == COUNTER_LEVEL and owed.side is OrderSide.SELL
    assert owed.paired_buy_price == D(110), "the intent kept the entry it completes"
    # The restart: the SELL had reached the exchange, so the reconcile finds it open and adopts it.
    restarted = grid_world(state=S.RECOVERING, runtime=saved, recovering_from=S.RUNNING)
    restarted.book.open = dict(world.book.open)
    sell = Order(_ADOPTED, SYMBOL, OrderSide.SELL, OrderType.LIMIT, owed.quantity)
    restarted.book.open[_ADOPTED] = replace(sell, price=D(120))
    restarted.derive(str(saved.inventory))
    restarted.hold(str(saved.inventory))

    restarted.executor.facts.reconcile_recovering()

    assert restarted.state() is S.RUNNING, restarted.runtime().reason_detail
    adopted = restarted.runtime().levels[COUNTER_LEVEL].order
    assert adopted is not None and adopted.paired_buy_price == D(110)
    restarted.fill(D(120), str(owed.quantity))
    assert restarted.runtime().completed_cycles == 1
    assert restarted.runtime().realised_profit > 0, "the cycle's profit is booked"


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


def test_a_counter_order_whose_request_faulted_leaves_no_entry_for_a_bot_in_error() -> (
    None
):
    """A fault ends in ERROR, whose only exit is a Stop that cancels the order: a leftover entry
    would be read by nothing and would keep the stopped bot from being deleted."""
    world = _running()
    world.book.raise_next.append(ConnectionError("read timed out"))

    world.fill(D(110), "2.272")

    assert world.state() is S.ERROR
    assert not world.runtime().held
