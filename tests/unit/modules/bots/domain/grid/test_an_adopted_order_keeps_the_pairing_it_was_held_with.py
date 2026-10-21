"""`BUG-265` - an order the reconcile adopts keeps the entry its held counter order carried.

@details A BUY fills while the bot is paused, so its SELL counter is held with the BUY's price as
its pairing. If that SELL reached the exchange before the app died and the reconcile adopts it
(`grid_reactions.adopted`), the adopted order replaced the held one and lost the pairing: its fill
booked into the inventory but closed no cycle, and Total PnL, which holds no grid profit, did not
show it.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_reactions import (
    LevelFill,
    adopted,
    on_fill,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridRuntime,
    LevelOrder,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.grid_runtime_builders import (
    STEP,
    order_id,
    started_ladder,
)

D = Decimal
_ADOPTED = "SEW-a3f9c1-0000000099"


def _after_a_buy_filled_while_paused() -> GridRuntime:
    """BUY at L1 (110) filled; its SELL counter at L2 (120) is held, paired with 110."""
    reaction = on_fill(
        started_ladder(), LevelFill(order_id(1), D(110), D(1)), STEP, hold=True
    )
    assert reaction.actions == ()
    (held,) = reaction.runtime.held
    assert held.paired_buy_price == D(110)
    return reaction.runtime


def _adoptee() -> LevelOrder:
    return LevelOrder(_ADOPTED, OrderSide.SELL, D(120), D(1))


def test_the_adopted_sell_closes_the_cycle_its_held_counter_would_have() -> None:
    runtime = adopted(_after_a_buy_filled_while_paused(), 2, _adoptee())

    done = on_fill(runtime, LevelFill(_ADOPTED, D(120), D(1)), STEP, hold=False)

    assert done.runtime.completed_cycles == 1
    assert done.runtime.realised_profit == 10, "bought at 110, sold at 120"
    assert done.runtime.held == ()


def test_the_held_order_is_still_dropped_when_it_is_adopted() -> None:
    runtime = adopted(_after_a_buy_filled_while_paused(), 2, _adoptee())

    assert runtime.held == ()
    assert runtime.level_of(_ADOPTED) is not None


def test_an_adopted_order_with_no_held_one_gets_no_invented_pairing() -> None:
    """The exchange's list says nothing of a pairing; an adopted opening-ladder SELL is not a
    cycle's completion, so none is made up."""
    runtime = adopted(started_ladder(), 2, _adoptee())

    done = on_fill(runtime, LevelFill(_ADOPTED, D(120), D(1)), STEP, hold=False)

    assert done.runtime.completed_cycles == 0
