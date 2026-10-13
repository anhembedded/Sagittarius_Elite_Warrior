"""`EPIC-039D` - a Futures owner's position, replayed from the venue's history."""

from __future__ import annotations

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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_history_reader import (
    FakeAccountHistoryReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trade_record import (
    TradeRecord,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.application.owner_position_world import (
    NOW,
    REGISTRATION,
    traded,
)

BUY, SELL = OrderSide.BUY, OrderSide.SELL


def _derive(*fills: tuple[OrderRecord, TradeRecord]) -> OwnerPositionDerivation:
    orders = [order for order, _ in fills]
    trades = [trade for _, trade in fills]
    reader = FakeAccountHistoryReader(orders, trades, now=NOW)
    return OwnerPositionDeriver().derive(REGISTRATION, reader, NOW)


def test_a_ladder_of_tagged_fills_derives_the_signed_position_and_entry() -> None:
    derivation = _derive(
        traded(1, BUY, "0.010", "60000"),
        traded(2, BUY, "0.020", "59000"),
        traded(3, SELL, "0.005", "61000", fee="0.12"),
    )

    position = derivation.position
    assert position.quantity == Decimal("0.025")
    assert position.average_entry == (
        Decimal("0.010") * 60000 + Decimal("0.020") * 59000
    ) / Decimal("0.030")
    assert position.fees == Decimal("0.12")
    assert derivation.counted(1001) and not derivation.counted(2000)


def test_a_flip_re_enters_at_the_flip_price() -> None:
    derivation = _derive(
        traded(1, BUY, "0.010", "60000"), traded(2, SELL, "0.030", "61000")
    )

    assert derivation.position.quantity == Decimal("-0.020")
    assert derivation.position.average_entry == Decimal(61000)


def test_an_order_without_the_owners_tag_is_not_the_owners() -> None:
    derivation = _derive(
        traded(1, BUY, "0.010", "60000"),
        traded(2, BUY, "5", "60000", client_order_id="autoclose-1"),
        traded(3, BUY, "7", "60000", client_order_id="SEW-b00000-0000000003"),
        traded(4, BUY, "9", "60000", client_order_id="SEW-0123456789ab"),
    )

    assert derivation.position.quantity == Decimal("0.010")
    assert derivation.fill_count == 1


def test_a_commission_in_another_asset_is_not_converted() -> None:
    derivation = _derive(traded(1, BUY, "0.010", "60000", fee="0.5", fee_asset="BNB"))

    assert derivation.position.fees == Decimal(0)


def test_nothing_traded_is_a_flat_position() -> None:
    derivation = _derive()

    assert (derivation.position.quantity, derivation.position.average_entry) == (
        Decimal(0),
        None,
    )


def test_a_run_older_than_the_venues_history_cannot_be_derived() -> None:
    reader = FakeAccountHistoryReader(now=NOW)
    old = REGISTRATION.__class__(
        REGISTRATION.owner_id,
        REGISTRATION.tag,
        REGISTRATION.symbol,
        NOW - timedelta(days=31),
        REGISTRATION.budget,
    )

    with pytest.raises(InventoryBeyondLookbackError):
        OwnerPositionDeriver().derive(old, reader, NOW)
