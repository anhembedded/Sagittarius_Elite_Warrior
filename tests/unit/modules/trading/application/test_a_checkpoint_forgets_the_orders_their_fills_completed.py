"""`BOT-228` - a checkpoint stops carrying an order once the fills it counted completed it.

@details The next read of the history starts after the orders a checkpoint carried were created, so
it never lists them and never sees one end: their ids stayed in `open_order_ids` for good (the
owner's `6tszoz` held 76 ids for 49 live orders). Now each carried id keeps what it still owes to
fill, the fills a read folds are subtracted, and the id goes when nothing is owed. An id goes only
on the owner's own counted fills, so an order that may still fill is never dropped.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.trading.adapters.persistence.json_owner_inventory_checkpoints import (
    JsonOwnerInventoryCheckpoints,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_inventory_deriver import (
    OwnerInventoryDeriver,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_owner_inventory_checkpoints import (
    OwnerInventoryCheckpoint,
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

D = Decimal
_RUN = datetime(2026, 10, 1, tzinfo=UTC)
_FIRST_READ = _RUN + timedelta(days=2)
_LATER = _FIRST_READ + timedelta(hours=1)
_LATEST = _FIRST_READ + timedelta(hours=2)
_QUANTITY = D("0.002")
_REGISTRATION = OwnerBudgetRegistration(
    owner_id="bot-1",
    tag="a3f9c1",
    symbol="BTCUSDT",
    run_started_at=_RUN,
    budget=OwnerBudget(
        10, D(1000), timedelta(milliseconds=250), 60, timedelta(minutes=1)
    ),
)


def _resting(exchange_id: int) -> OrderRecord:
    return OrderRecord(
        order=Order(
            client_order_id=ClientOrderId(f"SEW-a3f9c1-{exchange_id:010d}"),
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=_QUANTITY,
            status=OrderStatus.NEW,
            price=D(50000),
        ),
        executed_quantity=D(0),
        average_price=None,
        created_at=_RUN + timedelta(hours=1),
        exchange_order_id=exchange_id,
    )


def _fill(trade_id: int, order_id: int, quantity: Decimal, at: datetime) -> TradeRecord:
    return TradeRecord(
        symbol="BTCUSDT",
        trade_id=trade_id,
        order_id=order_id,
        side=OrderSide.BUY,
        price=D(50000),
        quantity=quantity,
        quote_quantity=quantity * 50000,
        fee=D(0),
        fee_asset="USDT",
        time=at,
    )


def _derive(
    checkpoints: FakeOwnerInventoryCheckpoints,
    orders: list[OrderRecord],
    trades: list[TradeRecord],
    now: datetime,
) -> OwnerInventory:
    history = FakeAccountHistoryReader(orders, trades, now=now)
    deriver = OwnerInventoryDeriver(checkpoints)
    return deriver.derive(_REGISTRATION, history, now).inventory


def _ten_orders_resting_at_the_first_checkpoint() -> FakeOwnerInventoryCheckpoints:
    checkpoints = FakeOwnerInventoryCheckpoints()
    _derive(checkpoints, [_resting(i) for i in range(1, 11)], [], _FIRST_READ)
    assert checkpoints.saved["a3f9c1"].open_order_ids == frozenset(range(1, 11))
    return checkpoints


def test_orders_filled_between_two_reads_leave_the_next_checkpoint() -> None:
    checkpoints = _ten_orders_resting_at_the_first_checkpoint()
    at = _FIRST_READ + timedelta(minutes=10)
    fills = [_fill(100 + i, i, _QUANTITY, at) for i in range(1, 8)]

    # The second read starts after the ten orders were created: it lists none of them.
    inventory = _derive(checkpoints, [], fills, _LATER)

    saved = checkpoints.saved["a3f9c1"]
    assert saved.open_order_ids == frozenset({8, 9, 10}), "the 76-for-49 case in small"
    assert inventory.quantity == 7 * _QUANTITY, "every fill was still folded, once"


def test_a_partly_filled_order_stays_until_the_rest_is_filled() -> None:
    checkpoints = _ten_orders_resting_at_the_first_checkpoint()
    half = _fill(100, 8, _QUANTITY / 2, _FIRST_READ + timedelta(minutes=10))
    _derive(checkpoints, [], [half], _LATER)

    after_half = checkpoints.saved["a3f9c1"]
    assert 8 in after_half.open_order_ids
    assert after_half.open_order_remaining[8] == _QUANTITY / 2

    rest = _fill(101, 8, _QUANTITY / 2, _LATER + timedelta(minutes=10))
    inventory = _derive(checkpoints, [], [half, rest], _LATEST)

    assert 8 not in checkpoints.saved["a3f9c1"].open_order_ids
    assert inventory.quantity == _QUANTITY, "the half read twice was counted once"


def test_an_order_with_no_fill_stays_because_nothing_says_it_ended() -> None:
    checkpoints = _ten_orders_resting_at_the_first_checkpoint()

    _derive(checkpoints, [], [], _LATER)

    assert checkpoints.saved["a3f9c1"].open_order_ids == frozenset(range(1, 11))


def test_an_id_an_older_checkpoint_carried_with_no_figure_stays() -> None:
    legacy = OwnerInventoryCheckpoint(
        tag="a3f9c1",
        run_started_at=_RUN,
        inventory=OwnerInventory(D(0), D(0)),
        last_trade_id=None,
        open_order_ids=frozenset({5}),
        read_from=_FIRST_READ,
    )
    checkpoints = FakeOwnerInventoryCheckpoints(legacy)
    fill = _fill(100, 5, _QUANTITY, _FIRST_READ + timedelta(minutes=10))

    inventory = _derive(checkpoints, [], [fill], _LATER)

    assert inventory.quantity == _QUANTITY, "its fill is still the owner's"
    assert checkpoints.saved["a3f9c1"].open_order_ids == frozenset({5})


def test_what_each_order_owes_survives_the_file(tmp_path: Path) -> None:
    checkpoint = OwnerInventoryCheckpoint(
        tag="a3f9c1",
        run_started_at=_RUN,
        inventory=OwnerInventory(D("0.001"), D(50)),
        last_trade_id=100,
        open_order_ids=frozenset({8, 9}),
        read_from=_LATER,
        open_order_remaining={8: D("0.001")},
    )
    store = JsonOwnerInventoryCheckpoints(tmp_path)

    store.save(checkpoint)

    assert store.load("a3f9c1") == checkpoint
