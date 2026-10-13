"""`EPIC-039H` - a Futures position checkpoint carries a run past the venue's 30-day history.

@details The same contract as Spot's inventory checkpoint (`test_owner_inventory_deriver.py`):
a derivation leaves one, the next reads only from it and counts the later fills of the orders that
were open then, one of another run is ignored, and a run past the lookback needs one.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_inventory_deriver import (
    InventoryBeyondLookbackError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_position_deriver import (
    OwnerPositionDerivation,
    OwnerPositionDeriver,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_record import (
    OrderRecord,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    OrderStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRegistration,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_history_reader import (
    FakeAccountHistoryReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_owner_position_checkpoints import (
    FakeOwnerPositionCheckpoints,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trade_record import (
    TradeRecord,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.application.owner_position_world import (
    REGISTRATION,
    RUN,
    TAG,
    traded,
)

BUY = OrderSide.BUY
_QTY = Decimal("0.010")


def _derive(
    fills: list[tuple[OrderRecord, TradeRecord]],
    checkpoints: FakeOwnerPositionCheckpoints,
    *,
    days_into_the_run: int = 1,
    registration: OwnerBudgetRegistration = REGISTRATION,
) -> OwnerPositionDerivation:
    now = registration.run_started_at + timedelta(days=days_into_the_run)
    reader = FakeAccountHistoryReader(
        [order for order, _ in fills], [trade for _, trade in fills], now=now
    )
    return OwnerPositionDeriver(checkpoints).derive(registration, reader, now)


def test_a_derivation_leaves_a_checkpoint_of_the_position_and_its_last_fill() -> None:
    checkpoints = FakeOwnerPositionCheckpoints()

    _derive([traded(1, BUY, "0.010", "60000")], checkpoints)

    saved = checkpoints.load(TAG)
    assert saved is not None
    assert (saved.position.quantity, saved.position.average_entry) == (
        _QTY,
        Decimal(60000),
    )
    assert saved.last_trade_id == 1001
    assert saved.run_started_at == RUN


def test_the_next_derivation_counts_a_fill_once_and_a_later_fill_of_an_open_order() -> (
    None
):
    checkpoints = FakeOwnerPositionCheckpoints()
    first = traded(1, BUY, "0.010", "60000")
    resting, _ = traded(2, BUY, "0.020", "59000")
    resting = replace(resting, order=replace(resting.order, status=OrderStatus.NEW))
    _derive([first, (resting, first[1])], checkpoints)

    filled = replace(resting, order=replace(resting.order, status=OrderStatus.FILLED))
    _, later_trade = traded(2, BUY, "0.020", "59000")
    later_trade = replace(later_trade, time=RUN + timedelta(days=1, hours=12))
    derivation = _derive(
        [first, (filled, later_trade)], checkpoints, days_into_the_run=2
    )

    assert derivation.position.quantity == Decimal("0.030")
    assert derivation.counted(1001), "counted by the checkpoint, not by this read"
    assert derivation.counted(1002)


def test_a_checkpoint_of_another_run_is_ignored_and_the_position_derived_in_full() -> (
    None
):
    checkpoints = FakeOwnerPositionCheckpoints()
    _derive([traded(1, BUY, "0.010", "60000")], checkpoints)
    stale = checkpoints.load(TAG)
    assert stale is not None
    checkpoints.save(
        replace(
            stale,
            run_started_at=RUN - timedelta(days=5),
            position=replace(stale.position, quantity=Decimal(9)),
        )
    )

    derivation = _derive([traded(1, BUY, "0.010", "60000")], checkpoints)

    assert derivation.position.quantity == _QTY


def test_a_run_past_the_lookback_is_refused_without_a_checkpoint() -> None:
    with pytest.raises(InventoryBeyondLookbackError):
        _derive([], FakeOwnerPositionCheckpoints(), days_into_the_run=31)


def test_a_checkpoint_carries_a_long_run_past_the_lookback() -> None:
    checkpoints = FakeOwnerPositionCheckpoints()
    _derive([traded(1, BUY, "0.010", "60000")], checkpoints, days_into_the_run=20)

    derivation = _derive([], checkpoints, days_into_the_run=40)

    assert derivation.position.quantity == _QTY
    assert derivation.position.average_entry == Decimal(60000)
