"""`EPIC-039L` — a close-position stop is in neither the open orders nor the send window.

@details It has no quantity, so it commits nothing; and a send that took a place in the
window would make the bot's next ladder order wait for the stop's spacing."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_order_ledger import (
    OwnerOrderLedger,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType

_NOW = datetime(2026, 10, 16, tzinfo=UTC)


def _order(number: int, *, close_position: bool) -> Order:
    return Order(
        client_order_id=ClientOrderId(f"SEW-a3f9c1-{number:010x}"),
        symbol="BTCUSDT",
        side=OrderSide.SELL,
        order_type=OrderType.STOP_MARKET,
        quantity=Decimal(0) if close_position else Decimal("0.01"),
        stop_price=Decimal(60000),
        close_position=close_position,
    )


def test_a_close_position_stop_neither_counts_as_open_nor_as_a_send() -> None:
    ledger = OwnerOrderLedger(timedelta(minutes=1))

    ledger.record_sent(_order(1, close_position=True), Decimal(0), _NOW)

    assert ledger.open_order_count == 0
    assert ledger.time_since_last_send(_NOW) is None
    assert ledger.orders_in_window(_NOW) == 0


def test_an_adopted_close_position_stop_is_not_open_either() -> None:
    ledger = OwnerOrderLedger(timedelta(minutes=1))

    ledger.adopt_open(_order(1, close_position=True), Decimal(0))

    assert ledger.open_order_count == 0


def test_an_ordinary_stop_is_still_open_and_a_send() -> None:
    ledger = OwnerOrderLedger(timedelta(minutes=1))

    ledger.record_sent(_order(2, close_position=False), Decimal(600), _NOW)

    assert ledger.open_order_count == 1
    assert ledger.orders_in_window(_NOW) == 1
