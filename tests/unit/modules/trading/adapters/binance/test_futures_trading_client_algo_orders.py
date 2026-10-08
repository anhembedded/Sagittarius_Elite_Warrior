"""`EPIC-028R` — the Futures client sends a stop-limit through the Algo
Order API and sees, cancels and lists algo orders alongside regular ones;
the history reader includes them.

@details The raw session is `Mock(spec=Client)`: specced from the installed
`python-binance` 1.0.37's own `Client`, so a call to a method the library
does not have fails here rather than on a live account."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from unittest.mock import Mock

import pytest
from binance.client import Client
from binance.exceptions import BinanceAPIException
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_history_reader import (
    FuturesHistoryReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_trading_client import (
    FuturesTradingClient,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.invalid_order_for_submission import (
    InvalidOrderForSubmissionError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_rejection_reason import (
    OrderRejectedByExchangeError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    OrderStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_submission_mode import (
    OrderSubmissionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    SymbolOrderMetadata,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.time_in_force import (
    TimeInForce,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
    ResolvedCredentials,
)

_NOW = datetime(2026, 10, 1, 12, tzinfo=UTC)
_ID = "SEW-a91f4c72e0b8"
_STOP = Order(
    client_order_id=ClientOrderId(_ID),
    symbol="BTCUSDT",
    side=OrderSide.BUY,
    order_type=OrderType.STOP_LIMIT,
    quantity=Decimal("0.002"),
    price=Decimal("65100.00"),
    stop_price=Decimal("65000.00"),
    time_in_force=TimeInForce.GTC,
)


def _api_error(code: int) -> BinanceAPIException:
    exc = BinanceAPIException.__new__(BinanceAPIException)
    exc.code = code
    exc.message = "Unknown order sent." if code == -2011 else "refused"
    exc.status_code = 400
    exc.response = None
    exc.request = None
    return exc


def _raw() -> Mock:
    raw = Mock(spec=Client)
    raw.timestamp_offset = 0
    raw.futures_get_open_orders.return_value = []
    raw.futures_get_open_algo_orders.return_value = []
    return raw


def _session_factory(raw: Mock) -> Mock:
    factory = Mock()
    factory.create_trading_client.return_value = raw
    return factory


def _credentials() -> Mock:
    provider = Mock()
    provider.resolve.return_value = ResolvedCredentials(
        ExchangeCredentials(api_key="key", api_secret="secret"), CredentialsSource.FILE
    )
    return provider


def _client(
    raw: Mock, mode: OrderSubmissionMode = OrderSubmissionMode.LIVE
) -> FuturesTradingClient:
    metadata = Mock()
    metadata.get_or_fetch.return_value = SymbolOrderMetadata(
        symbol="BTCUSDT",
        status="TRADING",
        step_size=Decimal("0.001"),
        tick_size=Decimal("0.01"),
        min_notional=Decimal(100),
        quantity_precision=3,
        price_precision=2,
        fetched_at=_NOW,
    )
    return FuturesTradingClient(_session_factory(raw), _credentials(), metadata, mode)


def _algo_row(status: str = "NEW", **changes: Any) -> dict[str, Any]:
    return {
        "algoId": 2146760,
        "clientAlgoId": _ID,
        "orderType": "STOP",
        "symbol": "BTCUSDT",
        "side": "BUY",
        "quantity": "0.002",
        "algoStatus": status,
        "triggerPrice": "65000.00",
        "price": "65100.00",
        "timeInForce": "GTC",
        "createTime": int(_NOW.timestamp() * 1000),
        **changes,
    }


def _regular_row(client_order_id: str = "SEW-regular") -> dict[str, Any]:
    return {
        "clientOrderId": client_order_id,
        "symbol": "BTCUSDT",
        "side": "SELL",
        "type": "LIMIT",
        "origQty": "0.001",
        "status": "NEW",
        "price": "70000",
        "timeInForce": "GTC",
    }


# -- placing ---------------------------------------------------------------- #


def test_a_stop_limit_goes_through_the_algo_order_api_only() -> None:
    raw = _raw()

    assert _client(raw).place_order(_STOP) is _STOP

    raw.futures_create_algo_order.assert_called_once()
    params = raw.futures_create_algo_order.call_args.kwargs
    assert params["clientAlgoId"] == _ID
    assert params["type"] == "STOP"
    assert params["triggerPrice"] == "65000.00"
    raw.futures_create_order.assert_not_called()


def test_a_stop_limit_cannot_be_validated_without_being_placed() -> None:
    raw = _raw()

    with pytest.raises(InvalidOrderForSubmissionError, match="no test endpoint"):
        _client(raw, OrderSubmissionMode.VALIDATE_ONLY).place_order(_STOP)

    raw.futures_create_algo_order.assert_not_called()
    raw.futures_create_test_order.assert_not_called()


def test_an_algo_refusal_is_the_exchanges_named_rejection() -> None:
    raw = _raw()
    raw.futures_create_algo_order.side_effect = _api_error(-2021)

    with pytest.raises(OrderRejectedByExchangeError):
        _client(raw).place_order(_STOP)


# -- listing and cancelling -------------------------------------------------- #


def test_open_orders_list_regular_and_algo_orders_together() -> None:
    raw = _raw()
    raw.futures_get_open_orders.return_value = [_regular_row()]
    raw.futures_get_open_algo_orders.return_value = [_algo_row()]

    orders = _client(raw).get_open_orders("BTCUSDT")

    assert [o.client_order_id for o in orders] == ["SEW-regular", _ID]
    assert orders[1].order_type is OrderType.STOP_LIMIT
    raw.futures_get_open_algo_orders.assert_called_once_with(symbol="BTCUSDT")


def test_a_regular_cancel_needs_one_request() -> None:
    raw = _raw()
    raw.futures_cancel_order.return_value = {
        **_regular_row(_ID),
        "status": "CANCELED",
    }

    order = _client(raw).cancel_order("BTCUSDT", _ID)

    assert order.status is OrderStatus.CANCELED
    raw.futures_cancel_algo_order.assert_not_called()


def test_an_id_the_regular_cancel_does_not_know_is_cancelled_as_an_algo_order() -> None:
    raw = _raw()
    raw.futures_cancel_order.side_effect = _api_error(-2011)
    raw.futures_get_algo_order.return_value = _algo_row("CANCELED")

    order = _client(raw).cancel_order("BTCUSDT", _ID)

    raw.futures_cancel_algo_order.assert_called_once_with(
        symbol="BTCUSDT", clientAlgoId=_ID
    )
    assert order.client_order_id == _ID
    assert order.status is OrderStatus.CANCELED


def test_an_id_neither_kind_knows_is_the_regular_refusal() -> None:
    raw = _raw()
    regular = _api_error(-2011)
    raw.futures_cancel_order.side_effect = regular
    raw.futures_cancel_algo_order.side_effect = _api_error(-2011)

    with pytest.raises(OrderRejectedByExchangeError) as raised:
        _client(raw).cancel_order("BTCUSDT", _ID)

    assert raised.value.__cause__ is regular
    raw.futures_get_algo_order.assert_not_called()


def test_another_cancel_refusal_is_not_retried_as_an_algo_order() -> None:
    raw = _raw()
    raw.futures_cancel_order.side_effect = _api_error(-1021)

    with pytest.raises(OrderRejectedByExchangeError):
        _client(raw).cancel_order("BTCUSDT", _ID)

    raw.futures_cancel_algo_order.assert_not_called()


def test_cancel_all_clears_both_lists_even_when_none_was_seen() -> None:
    """An algo order placed between the read and the cancel is cancelled
    too: the algo cancel-all always runs."""
    raw = _raw()

    assert _client(raw).cancel_all_orders("BTCUSDT") == []

    raw.futures_cancel_all_open_orders.assert_called_once_with(symbol="BTCUSDT")
    raw.futures_cancel_all_algo_open_orders.assert_called_once_with(symbol="BTCUSDT")


def test_cancel_all_reports_the_algo_orders_it_cancelled() -> None:
    raw = _raw()
    raw.futures_get_open_algo_orders.return_value = [_algo_row()]

    cancelled = _client(raw).cancel_all_orders("BTCUSDT")

    assert [o.client_order_id for o in cancelled] == [_ID]


# -- history ---------------------------------------------------------------- #


def test_order_history_includes_algo_orders_read_100_rows_at_a_time() -> None:
    raw = _raw()
    raw.futures_get_all_orders.return_value = []
    raw.futures_get_all_algo_orders.return_value = [_algo_row("FINISHED")]
    reader = FuturesHistoryReader(_session_factory(raw), _credentials(), lambda: _NOW)

    records = reader.order_history("BTCUSDT", _NOW - timedelta(hours=1))

    assert [r.order.client_order_id for r in records] == [_ID]
    assert records[0].order.status is OrderStatus.TRIGGERED
    assert records[0].executed_quantity == 0
    call = raw.futures_get_all_algo_orders.call_args.kwargs
    assert call["symbol"] == "BTCUSDT"
    assert call["limit"] == 100


def test_a_regular_cancelled_order_is_unchanged_by_the_algo_path() -> None:
    # The regular path's mapping still reads `stopPrice`, not `triggerPrice`.
    raw = _raw()
    raw.futures_cancel_order.return_value = {
        **_regular_row(_ID),
        "status": "CANCELED",
        "stopPrice": "0",
    }

    order = _client(raw).cancel_order("BTCUSDT", _ID)

    assert replace(order, status=OrderStatus.NEW).stop_price is None
