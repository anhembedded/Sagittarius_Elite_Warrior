"""`EPIC-029` ADR D6 — the inventory comes from the exchange.

@details The history is a `FakeAccountHistoryReader` (the port's own fake),
arranged with the orders and fills a test names; nothing the owner says
about itself is an input.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_inventory_deriver import (
    InventoryBeyondLookbackError,
    OwnerInventoryDeriver,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_record import (
    OrderRecord,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    OrderStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerBudget,
    OwnerInventory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRegistration,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_history_reader import (
    FakeAccountHistoryReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_owner_inventory_checkpoints import (
    FakeOwnerInventoryCheckpoints,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trade_record import (
    TradeRecord,
)

_RUN = datetime(2026, 10, 1, tzinfo=UTC)
_NOW = _RUN + timedelta(days=2)
_REGISTRATION = OwnerBudgetRegistration(
    owner_id="bot-1",
    tag="a3f9c1",
    symbol="BTCUSDT",
    run_started_at=_RUN,
    budget=OwnerBudget(
        10, Decimal(1000), timedelta(milliseconds=250), 60, timedelta(minutes=1)
    ),
)


def _order(
    exchange_id: int,
    client_id: str = "SEW-a3f9c1-0000000001",
    created: datetime = _RUN + timedelta(hours=1),
    status: OrderStatus = OrderStatus.FILLED,
) -> OrderRecord:
    return OrderRecord(
        order=Order(
            client_order_id=ClientOrderId(client_id),
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("0.002"),
            status=status,
            price=Decimal(50000),
        ),
        executed_quantity=Decimal("0.002"),
        average_price=Decimal(50000),
        created_at=created,
        exchange_order_id=exchange_id,
    )


def _trade(
    trade_id: int,
    order_id: int,
    side: OrderSide = OrderSide.BUY,
    fee: tuple[str, str] = ("0.1", "USDT"),
    time: datetime = _RUN + timedelta(hours=2),
) -> TradeRecord:
    return TradeRecord(
        symbol="BTCUSDT",
        trade_id=trade_id,
        order_id=order_id,
        side=side,
        price=Decimal(50000),
        quantity=Decimal("0.002"),
        quote_quantity=Decimal(100),
        fee=Decimal(fee[0]),
        fee_asset=fee[1],
        time=time,
    )


def _derive(
    orders: list[OrderRecord],
    trades: list[TradeRecord],
    checkpoints: FakeOwnerInventoryCheckpoints | None = None,
    now: datetime = _NOW,
) -> OwnerInventory:
    history = FakeAccountHistoryReader(orders, trades, now=now)
    deriver = OwnerInventoryDeriver(checkpoints or FakeOwnerInventoryCheckpoints())
    return deriver.derive(_REGISTRATION, history, now)


def test_only_the_owners_tagged_fills_count() -> None:
    inventory = _derive(
        [
            _order(1),
            _order(2, client_id="web_3f9a1c2b7d4e4b0c"),
            _order(3, client_id="SEW-b00000-0000000003"),
        ],
        [_trade(10, 1), _trade(11, 2), _trade(12, 3)],
    )
    assert inventory == OwnerInventory(Decimal("0.002"), Decimal(100))


def test_a_fee_in_the_base_asset_is_subtracted() -> None:
    inventory = _derive([_order(1)], [_trade(10, 1, fee=("0.000002", "BTC"))])
    assert inventory.quantity == Decimal("0.001998")


def test_a_fee_in_bnb_is_not() -> None:
    inventory = _derive([_order(1)], [_trade(10, 1, fee=("0.0001", "BNB"))])
    assert inventory.quantity == Decimal("0.002")


def test_base_a_previous_run_kept_is_not_counted() -> None:
    """Stop with *keep base*: the coins are the user's now (ADR D6 r2)."""
    earlier = _RUN - timedelta(days=1)
    inventory = _derive(
        [_order(1, created=earlier)], [_trade(10, 1, time=earlier + timedelta(hours=1))]
    )
    assert inventory == OwnerInventory(Decimal(0), Decimal(0))


def test_a_sell_takes_its_share_of_the_inventory() -> None:
    inventory = _derive(
        [_order(1), _order(2, client_id="SEW-a3f9c1-0000000002")],
        [
            _trade(10, 1),
            _trade(11, 1),
            _trade(12, 2, side=OrderSide.SELL, time=_RUN + timedelta(hours=3)),
        ],
    )
    assert inventory == OwnerInventory(Decimal("0.002"), Decimal(100))


class TestCheckpoint:
    def test_a_derivation_leaves_a_checkpoint(self) -> None:
        checkpoints = FakeOwnerInventoryCheckpoints()
        _derive([_order(1)], [_trade(10, 1)], checkpoints)

        saved = checkpoints.load("a3f9c1")
        assert saved is not None
        assert (saved.inventory, saved.last_trade_id) == (
            OwnerInventory(Decimal("0.002"), Decimal(100)),
            10,
        )
        assert saved.read_from == _NOW - timedelta(minutes=1)

    def test_the_next_derivation_reads_only_from_it(self) -> None:
        """A fill counted before is not counted again; a later fill of an
        order that was open at the checkpoint is counted, though the order
        was created before the next read starts."""
        checkpoints = FakeOwnerInventoryCheckpoints()
        resting = _order(2, client_id="SEW-a3f9c1-0000000002", status=OrderStatus.NEW)
        _derive([_order(1), resting], [_trade(10, 1)], checkpoints)

        later = _NOW + timedelta(days=1)
        inventory = _derive(
            [
                _order(1),
                replace(
                    resting, order=replace(resting.order, status=OrderStatus.FILLED)
                ),
            ],
            [_trade(10, 1), _trade(11, 2, time=later - timedelta(hours=1))],
            checkpoints,
            now=later,
        )
        assert inventory == OwnerInventory(Decimal("0.004"), Decimal(200))

    def test_a_checkpoint_of_another_run_is_ignored(self) -> None:
        checkpoints = FakeOwnerInventoryCheckpoints()
        _derive([_order(1)], [_trade(10, 1)], checkpoints)
        stale = checkpoints.load("a3f9c1")
        assert stale is not None
        checkpoints.save(
            replace(
                stale,
                run_started_at=_RUN - timedelta(days=5),
                inventory=OwnerInventory(Decimal(9), Decimal(9)),
            )
        )

        inventory = _derive([_order(1)], [_trade(10, 1)], checkpoints)

        assert inventory == OwnerInventory(Decimal("0.002"), Decimal(100))

    def test_a_run_past_the_lookback_needs_a_checkpoint(self) -> None:
        long_after = _RUN + timedelta(days=31)
        with pytest.raises(InventoryBeyondLookbackError):
            _derive([], [], now=long_after)

    def test_a_checkpoint_carries_a_long_run_past_the_lookback(self) -> None:
        checkpoints = FakeOwnerInventoryCheckpoints()
        _derive(
            [_order(1)], [_trade(10, 1)], checkpoints, now=_RUN + timedelta(days=20)
        )

        inventory = _derive([], [], checkpoints, now=_RUN + timedelta(days=40))

        assert inventory == OwnerInventory(Decimal("0.002"), Decimal(100))
