"""`EPIC-035H` — a read-only copy of the app sends no order and cancels none.

Every order that leaves the app, a bot's and a person's, is made by a client the
venue's factory hands out, so wrapping the factory is the one place that covers
them all. Reads pass through; a test order (`VALIDATE_ONLY`) places nothing and
passes too.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.errors import ReadOnlyInstanceError
from Sagittarius_Elite_Warrior.src.infrastructure.instance.instance_access import (
    InstanceAccess,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.read_only_trading_client_factory import (
    ReadOnlyTradingClientFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_client import (
    ITradingClient,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_client_factory import (
    ITradingClientFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.live_position import (
    LivePosition,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_submission_mode import (
    OrderSubmissionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType

_ORDER = Order("SEW-1", "BTCUSDT", OrderSide.BUY, OrderType.MARKET, Decimal(1))


class _Client(ITradingClient):
    def __init__(self, mode: OrderSubmissionMode) -> None:
        self.mode = mode
        self.calls: list[str] = []

    def place_order(self, order: Order) -> Order:
        self.calls.append("place")
        return order

    def find_order(self, symbol: str, client_order_id: str) -> Order | None:
        self.calls.append("find")
        return _ORDER

    def cancel_order(self, symbol: str, client_order_id: str) -> Order:
        self.calls.append("cancel")
        return _ORDER

    def cancel_all_orders(self, symbol: str) -> list[Order]:
        self.calls.append("cancel_all")
        return [_ORDER]

    def get_open_orders(self, symbol: str | None = None) -> list[Order]:
        self.calls.append("open_orders")
        return [_ORDER]

    def get_positions(self, symbol: str | None = None) -> list[LivePosition]:
        self.calls.append("positions")
        return []


class _Factory(ITradingClientFactory):
    def __init__(self) -> None:
        self.clients: list[_Client] = []

    def create(self, mode: OrderSubmissionMode) -> ITradingClient:
        client = _Client(mode)
        self.clients.append(client)
        return client

    def accepted_order_types(self) -> frozenset[OrderType]:
        return frozenset({OrderType.MARKET})


def _read_only(inner: _Factory) -> ReadOnlyTradingClientFactory:
    reason = "Another copy is running; this one is read-only."
    return ReadOnlyTradingClientFactory(inner, reason)


def test_a_read_only_instance_places_no_live_order() -> None:
    inner = _Factory()
    client = _read_only(inner).create(OrderSubmissionMode.LIVE)

    with pytest.raises(ReadOnlyInstanceError, match="read-only"):
        client.place_order(_ORDER)

    assert inner.clients[0].calls == []


def test_a_read_only_instance_cancels_nothing() -> None:
    inner = _Factory()
    client = _read_only(inner).create(OrderSubmissionMode.LIVE)

    with pytest.raises(ReadOnlyInstanceError):
        client.cancel_order("BTCUSDT", "SEW-1")
    with pytest.raises(ReadOnlyInstanceError):
        client.cancel_all_orders("BTCUSDT")

    assert inner.clients[0].calls == []


@pytest.mark.parametrize("mode", list(OrderSubmissionMode))
def test_a_cancel_is_refused_whatever_the_mode(mode: OrderSubmissionMode) -> None:
    client = _read_only(_Factory()).create(mode)

    with pytest.raises(ReadOnlyInstanceError):
        client.cancel_order("BTCUSDT", "SEW-1")


def test_a_test_order_places_nothing_and_goes_through() -> None:
    inner = _Factory()
    client = _read_only(inner).create(OrderSubmissionMode.VALIDATE_ONLY)

    assert client.place_order(_ORDER) is _ORDER
    assert inner.clients[0].calls == ["place"]


def test_reads_go_through_in_every_mode() -> None:
    inner = _Factory()
    client = _read_only(inner).create(OrderSubmissionMode.LIVE)

    assert client.find_order("BTCUSDT", "SEW-1") is _ORDER
    assert client.get_open_orders() == [_ORDER]
    assert client.get_positions() == []
    assert inner.clients[0].calls == ["find", "open_orders", "positions"]


def test_the_accepted_order_types_are_the_venues() -> None:
    assert _read_only(_Factory()).accepted_order_types() == frozenset(
        {OrderType.MARKET}
    )


def test_the_refusal_carries_the_instances_own_reason(tmp_path: Path) -> None:
    first = InstanceAccess.acquire(tmp_path / "instance.lock")
    second = InstanceAccess.acquire(tmp_path / "instance.lock")
    client = ReadOnlyTradingClientFactory(_Factory(), second.reason).create(
        OrderSubmissionMode.LIVE
    )

    with pytest.raises(ReadOnlyInstanceError) as caught:
        client.place_order(_ORDER)

    assert str(caught.value) == second.reason
    first.release()
