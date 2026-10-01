"""`EPIC-028R` — a Futures stop-limit as an Algo Order API request, and an
algo order (REST or `ALGO_UPDATE`) read back as a domain `Order`.

@details The payloads are Binance's documented USD-M Algo Order shapes; no
live call verified them (the same disclosure as the adapters)."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.algo_order_links import (
    AlgoOrderLinks,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.algo_update_parser import (
    order_trade_update_order_id,
    parse_algo_update,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_algo_order_mapper import (
    is_algo_routed,
    map_futures_algo_history_order,
    map_futures_algo_payload_to_order,
    map_order_to_futures_algo_params,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.invalid_order_for_submission import (
    InvalidOrderForSubmissionError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    OrderStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    SymbolOrderMetadata,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.time_in_force import (
    TimeInForce,
)

_METADATA = SymbolOrderMetadata(
    symbol="BTCUSDT",
    status="TRADING",
    step_size=Decimal("0.001"),
    tick_size=Decimal("0.1"),
    min_notional=Decimal(100),
    quantity_precision=3,
    price_precision=1,
    fetched_at=datetime(2026, 10, 1, tzinfo=UTC),
)
_STOP = Order(
    client_order_id=ClientOrderId("SEW-a91f4c72e0b8"),
    symbol="BTCUSDT",
    side=OrderSide.BUY,
    order_type=OrderType.STOP_LIMIT,
    quantity=Decimal("0.002"),
    price=Decimal("65100.0"),
    stop_price=Decimal("65000.0"),
    time_in_force=TimeInForce.GTC,
)


def _algo_payload(**changes: Any) -> dict[str, Any]:
    """`GET /fapi/v1/algoOrder`'s documented answer."""
    return {
        "algoId": 2146760,
        "clientAlgoId": "SEW-a91f4c72e0b8",
        "algoType": "CONDITIONAL",
        "orderType": "STOP",
        "symbol": "BTCUSDT",
        "side": "BUY",
        "positionSide": "BOTH",
        "timeInForce": "GTC",
        "quantity": "0.002",
        "algoStatus": "NEW",
        "triggerPrice": "65000.0",
        "price": "65100.0",
        "workingType": "CONTRACT_PRICE",
        "reduceOnly": False,
        "createTime": 1759320000000,
        "updateTime": 1759320000500,
        "triggerTime": 0,
        **changes,
    }


# -- sending ---------------------------------------------------------------- #


def test_a_stop_limit_is_sent_with_the_apps_id_as_its_client_algo_id() -> None:
    assert map_order_to_futures_algo_params(_STOP, _METADATA) == {
        "algoType": "CONDITIONAL",
        "symbol": "BTCUSDT",
        "side": "BUY",
        "positionSide": "BOTH",
        "type": "STOP",
        "quantity": "0.002",
        "price": "65100.0",
        "triggerPrice": "65000.0",
        "timeInForce": "GTC",
        "workingType": "CONTRACT_PRICE",
        "reduceOnly": False,
        "clientAlgoId": "SEW-a91f4c72e0b8",
    }


def test_only_the_stop_limit_is_algo_routed() -> None:
    assert [t for t in OrderType if is_algo_routed(t)] == [OrderType.STOP_LIMIT]


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"order_type": OrderType.LIMIT}, "not sent through the Algo Order API"),
        ({"stop_price": None}, "stop price and its limit price"),
        ({"price": None}, "stop price and its limit price"),
        ({"time_in_force": None}, "time in force"),
        ({"quantity": Decimal("0.0025")}, "quantity 0.0025 is not a multiple"),
        ({"price": Decimal("65100.05")}, "price 65100.05 is not a multiple"),
        ({"stop_price": Decimal("65000.05")}, "stop price 65000.05 is not a multiple"),
    ],
)
def test_an_incomplete_or_unrounded_stop_limit_is_refused(
    changes: dict[str, Any], message: str
) -> None:
    with pytest.raises(InvalidOrderForSubmissionError, match=message):
        map_order_to_futures_algo_params(replace(_STOP, **changes), _METADATA)


# -- reading ---------------------------------------------------------------- #


def test_an_algo_order_reads_back_as_the_order_the_app_placed() -> None:
    order = map_futures_algo_payload_to_order(_algo_payload())

    assert order.client_order_id == _STOP.client_order_id
    assert order.order_type is OrderType.STOP_LIMIT
    assert order.status is OrderStatus.NEW
    assert (order.quantity, order.price, order.stop_price) == (
        _STOP.quantity,
        _STOP.price,
        _STOP.stop_price,
    )
    assert order.time_in_force is TimeInForce.GTC
    assert order.order_time == datetime.fromtimestamp(1759320000.5, tz=UTC)


@pytest.mark.parametrize(
    ("algo_status", "status"),
    [
        ("NEW", OrderStatus.NEW),
        ("TRIGGERING", OrderStatus.NEW),
        ("TRIGGERED", OrderStatus.TRIGGERED),
        ("FINISHED", OrderStatus.TRIGGERED),
        ("CANCELED", OrderStatus.CANCELED),
        ("REJECTED", OrderStatus.REJECTED),
        ("EXPIRED", OrderStatus.EXPIRED),
        ("SOMETHING_NEW", OrderStatus.UNKNOWN),
    ],
)
def test_each_algo_status_has_its_meaning(
    algo_status: str, status: OrderStatus
) -> None:
    payload = _algo_payload(algoStatus=algo_status)

    assert map_futures_algo_payload_to_order(payload).status is status


@pytest.mark.parametrize(
    ("raw", "order_type"),
    [
        ("STOP", OrderType.STOP_LIMIT),
        ("STOP_MARKET", OrderType.STOP_MARKET),
        ("TAKE_PROFIT_MARKET", OrderType.TAKE_PROFIT_MARKET),
        # Placed in Binance's own UI: no member, but never lost (`BUG-091`).
        ("TAKE_PROFIT", OrderType.UNKNOWN),
    ],
)
def test_an_algo_order_placed_anywhere_is_read(raw: str, order_type: OrderType) -> None:
    payload = _algo_payload(orderType=raw, clientAlgoId="web_x1")

    assert map_futures_algo_payload_to_order(payload).order_type is order_type


def test_an_algo_history_row_carries_no_fill_of_its_own() -> None:
    record = map_futures_algo_history_order(_algo_payload(algoStatus="FINISHED"))

    assert record.order.status is OrderStatus.TRIGGERED
    assert record.executed_quantity == 0
    assert record.average_price is None
    assert record.created_at == datetime.fromtimestamp(1759320000, tz=UTC)


def test_an_algo_history_row_without_a_creation_time_is_malformed() -> None:
    with pytest.raises(KeyError):
        map_futures_algo_history_order(_algo_payload(createTime=0))


# -- the user-data stream --------------------------------------------------- #


def _algo_update(status: str, placed: object) -> dict[str, Any]:
    """Binance's documented `ALGO_UPDATE`."""
    return {
        "e": "ALGO_UPDATE",
        "T": 1759320100000,
        "E": 1759320100005,
        "o": {
            "caid": "SEW-a91f4c72e0b8",
            "aid": 2146760,
            "at": "CONDITIONAL",
            "o": "STOP",
            "s": "BTCUSDT",
            "S": "BUY",
            "ps": "BOTH",
            "f": "GTC",
            "q": "0.002",
            "X": status,
            "ai": placed,
            "tp": "65000.0",
            "p": "65100.0",
            "R": False,
        },
    }


def test_a_triggered_algo_update_names_the_order_it_placed() -> None:
    update = parse_algo_update(_algo_update("TRIGGERED", "8389765519"))

    assert update.order.client_order_id == _STOP.client_order_id
    assert update.order.status is OrderStatus.TRIGGERED
    assert update.order.stop_price == Decimal("65000.0")
    assert update.placed_order_id == 8389765519


@pytest.mark.parametrize("placed", ["", None, 0])
def test_an_untriggered_algo_update_names_no_order(placed: object) -> None:
    update = parse_algo_update(_algo_update("NEW", placed))

    assert update.order.status is OrderStatus.NEW
    assert update.placed_order_id is None


def test_an_order_trade_update_names_its_exchange_order_id() -> None:
    assert order_trade_update_order_id({"o": {"i": 8389765519}}) == 8389765519
    assert order_trade_update_order_id({"o": {}}) is None


def test_links_forget_the_oldest_first() -> None:
    links = AlgoOrderLinks(capacity=2)
    links.remember(1, ClientOrderId("SEW-1"))
    links.remember(2, ClientOrderId("SEW-2"))
    links.remember(1, ClientOrderId("SEW-1"))  # refreshed: now the newest
    links.remember(3, ClientOrderId("SEW-3"))

    assert links.client_order_id_for(1) == "SEW-1"
    assert links.client_order_id_for(2) is None
    assert links.client_order_id_for(3) == "SEW-3"


def test_links_need_room_for_one() -> None:
    with pytest.raises(ValueError, match="capacity"):
        AlgoOrderLinks(capacity=0)
