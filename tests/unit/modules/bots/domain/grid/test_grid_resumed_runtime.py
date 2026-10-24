"""`BUG-268` - a resume replaces the ladder, never the run (`resumed_runtime`).

The owner's Futures bot went AWAITING_RECOVERY -> STARTING -> RUNNING once and showed 0.50 of
fees for a run that had paid about 2.13: the restart rebuilt the runtime from a list of fields to
keep, and `commissions` was not on it. Its cost was also replaced by trading's, which holds no
quote fee, so every later sell booked about 0.17 too much.
"""

from __future__ import annotations

from dataclasses import fields
from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_resumed_runtime import (
    LADDER_FIELDS,
    resumed_runtime,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
    GridRuntime,
    HeldOrder,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.protective_stop import (
    ProtectiveStop,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.protective_stop_fsm_matrix import (
    ProtectiveStopState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerInventory,
)

from .grid_runtime_builders import empty_ladder, started_ladder

_HELD = Decimal("2.28")
#: The run's cost of what it holds, the fees its buys paid included.
_COST_WITH_FEES = Decimal("1682.8905119904")
#: Trading's cost of the same holding: the quote paid, no quote fee.
_COST_WITHOUT_FEES = Decimal("1682.72")
_STOP = ProtectiveStop(
    "SEW-a3f9c1-stop000001", OrderSide.SELL, Decimal(700), ProtectiveStopState.STANDING
)


def _earned() -> GridRuntime:
    """A halted run with every field away from its default, so a field a resume drops shows."""
    return GridRuntime(
        levels=started_ladder().levels,
        inventory=_HELD,
        cost=_COST_WITH_FEES,
        realised_profit=Decimal("6.81057812"),
        completed_cycles=7,
        realised_total=Decimal("21.0051855904"),
        earlier_runs_base=Decimal("0.5"),
        earlier_runs_cost=Decimal(367),
        start_price=Decimal("734.23"),
        mark_price=Decimal("732.92"),
        mark_price_at=datetime(2026, 10, 24, 2, 19, tzinfo=UTC),
        maker_fee=Decimal("0.0002"),
        unpriced_fees=1,
        commissions=Decimal("1.6309"),
        funding_total=Decimal("-0.42"),
        held=(HeldOrder(2, OrderSide.BUY, Decimal(1)),),
        reason=GridReason.RATE_LIMITED,
        reason_detail="L5 SELL: rate limited",
        sell_base_on_stop=True,
        entry_side=OrderSide.SELL,
        protective_stops=(_STOP,),
    )


def test_every_field_of_the_earned_run_is_set_away_from_its_default() -> None:
    """The fixture's own guard: a field added to `GridRuntime` must be set in `_earned`, or the
    test below cannot see a resume drop it."""
    default = GridRuntime(())
    earned = _earned()
    unset = [
        f.name
        for f in fields(GridRuntime)
        if getattr(earned, f.name) == getattr(default, f.name)
    ]
    assert unset == []


def test_a_resume_keeps_every_field_the_ladder_does_not_own() -> None:
    earned = _earned()
    resumed = resumed_runtime(
        earned, empty_ladder(), OwnerInventory(_HELD, _COST_WITHOUT_FEES)
    )
    dropped = [
        f.name
        for f in fields(GridRuntime)
        if f.name not in LADDER_FIELDS
        and getattr(resumed, f.name) != getattr(earned, f.name)
    ]
    assert dropped == []
    assert resumed.commissions == Decimal("1.6309")
    assert resumed.funding_total == Decimal("-0.42")
    assert resumed.protective_stops == (_STOP,)


def test_the_ladder_fields_are_the_new_ladders() -> None:
    ladder = empty_ladder()
    resumed = resumed_runtime(
        _earned(), ladder, OwnerInventory(_HELD, _COST_WITHOUT_FEES)
    )
    assert {name: getattr(resumed, name) for name in LADDER_FIELDS} == {
        name: getattr(ladder, name) for name in LADDER_FIELDS
    }


def test_an_unchanged_holding_keeps_the_cost_its_fees_are_in() -> None:
    resumed = resumed_runtime(
        _earned(), empty_ladder(), OwnerInventory(_HELD, _COST_WITHOUT_FEES)
    )
    assert resumed.inventory == _HELD
    assert resumed.cost == _COST_WITH_FEES


def test_a_holding_that_changed_takes_tradings_inventory_and_cost() -> None:
    resumed = resumed_runtime(
        _earned(), empty_ladder(), OwnerInventory(Decimal("1.9"), Decimal(1400))
    )
    assert resumed.inventory == Decimal("1.9")
    assert resumed.cost == Decimal(1400)


def test_a_run_with_no_start_price_takes_the_ladders() -> None:
    earned = GridRuntime((), inventory=_HELD, cost=_COST_WITH_FEES)
    ladder = GridRuntime(empty_ladder().levels, start_price=Decimal(120))
    resumed = resumed_runtime(earned, ladder, OwnerInventory(_HELD, _COST_WITHOUT_FEES))
    assert resumed.start_price == Decimal(120)
