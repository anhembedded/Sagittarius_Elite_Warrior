"""`BUG-214` - the order a reconcile applies missed fills in is the exchange's.

@details The key sorts by the time of an order's newest trade, the trade id breaking a
tie (the fake and Binance stamp whole milliseconds), and leaves undated fills last.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.recovery.grid_missed_fills import (
    MissedFill,
    event_order,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    LevelOrder,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_record import (
    OrderRecord,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trade_record import (
    TradeRecord,
)

D = Decimal
_T0 = datetime(2026, 10, 15, 9, tzinfo=UTC)


def _trade(trade_id: int, order_id: int, seconds: int) -> TradeRecord:
    return TradeRecord(
        "BTCUSDT", trade_id, order_id, OrderSide.BUY, D(100), D(1), D(100),
        D(0), "USDT", _T0 + timedelta(seconds=seconds),
    )  # fmt: skip


def _missed(name: str, *trades: TradeRecord) -> MissedFill:
    order = Order(
        ClientOrderId(name), "BTCUSDT", OrderSide.BUY, OrderType.LIMIT, D(1), D(100)
    )
    record = OrderRecord(order, D(1), D(100), _T0, 1)
    return MissedFill(
        LevelOrder(name, OrderSide.BUY, D(100), D(1)), record, D(1), trades
    )


def _sorted(*found: MissedFill) -> list[str]:
    return [f.saved.client_order_id for f in sorted(found, key=event_order)]


def test_the_fill_that_finished_first_is_applied_first_whatever_its_level() -> None:
    low = _missed("low", _trade(2, 1, seconds=5))
    high = _missed("high", _trade(1, 2, seconds=1))
    assert _sorted(low, high) == ["high", "low"]


def test_an_order_is_dated_by_its_newest_trade() -> None:
    slow = _missed("slow", _trade(1, 1, seconds=0), _trade(4, 1, seconds=9))
    quick = _missed("quick", _trade(2, 2, seconds=3))
    assert _sorted(slow, quick) == ["quick", "slow"]


def test_trades_in_the_same_instant_are_ordered_by_trade_id() -> None:
    first = _missed("first", _trade(7, 1, seconds=2))
    second = _missed("second", _trade(8, 2, seconds=2))
    assert _sorted(second, first) == ["first", "second"]


def test_a_fill_history_does_not_date_goes_last_in_the_order_given() -> None:
    undated_a = _missed("undated-a")
    undated_b = _missed("undated-b")
    dated = _missed("dated", _trade(1, 3, seconds=1))
    assert _sorted(undated_a, undated_b, dated) == ["dated", "undated-a", "undated-b"]
