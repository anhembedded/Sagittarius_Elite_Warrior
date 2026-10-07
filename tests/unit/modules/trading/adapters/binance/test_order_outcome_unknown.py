"""BUG-170 — a live submission with no readable answer is "outcome unknown", never "rejected".

python-binance turns a non-JSON answer (a gateway's `502` page) into
`BinanceAPIException(code=0)`; a dropped connection is a `requests` error. Both
leave the question "did the order arrive?" open, and a rejection says it did
not. The adapters raise `OrderOutcomeUnknownError` for them while sending live,
and answer a read by client order id (`find_order`) to settle it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest
from binance.exceptions import BinanceAPIException, BinanceRequestException
from requests.exceptions import ReadTimeout
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_trading_client import (
    FuturesTradingClient,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_trading_client import (
    SpotTradingClient,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_client import (
    ITradingClient,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_outcome_unknown import (
    OrderOutcomeUnknownError,
)
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
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
    ResolvedCredentials,
)

_ID = "SEW-a91f4c72e0b8"
_ORDER = Order(
    client_order_id=ClientOrderId(_ID),
    symbol="BTCUSDT",
    side=OrderSide.BUY,
    order_type=OrderType.MARKET,
    quantity=Decimal("0.002"),
)
_PAGE = "<html><head><title>502 Bad Gateway</title></head><body>nginx</body></html>"
_UNKNOWN_ORDER = -2013


def _html_answer() -> BinanceAPIException:
    return BinanceAPIException(SimpleNamespace(text=_PAGE), 502, _PAGE)


def _api_error(code: int, message: str) -> BinanceAPIException:
    exc = BinanceAPIException.__new__(BinanceAPIException)
    exc.code, exc.message, exc.status_code = code, message, 400
    exc.response = exc.request = None
    return exc


def _row() -> dict[str, Any]:
    return {
        "clientOrderId": _ID,
        "symbol": "BTCUSDT",
        "side": "BUY",
        "type": "MARKET",
        "origQty": "0.002",
        "status": "FILLED",
    }


def _build(venue: str, raw: Mock, mode: OrderSubmissionMode) -> ITradingClient:
    sessions = Mock()
    sessions.create_trading_client.return_value = raw
    credentials = Mock()
    credentials.resolve.return_value = ResolvedCredentials(
        ExchangeCredentials(api_key="key", api_secret="secret"), CredentialsSource.FILE
    )
    metadata = Mock()
    metadata.get_or_fetch.return_value = SymbolOrderMetadata(
        symbol="BTCUSDT",
        status="TRADING",
        step_size=Decimal("0.001"),
        tick_size=Decimal("0.01"),
        min_notional=Decimal(100),
        quantity_precision=3,
        price_precision=2,
        fetched_at=datetime(2026, 8, 27, tzinfo=UTC),
    )
    cls = FuturesTradingClient if venue == "futures" else SpotTradingClient
    return cls(sessions, credentials, metadata, mode)


def _create(venue: str, raw: Mock) -> Mock:
    return raw.futures_create_order if venue == "futures" else raw.create_order


def _get(venue: str, raw: Mock) -> Mock:
    return raw.futures_get_order if venue == "futures" else raw.get_order


@pytest.fixture(params=["futures", "spot"])
def venue(request: pytest.FixtureRequest) -> str:
    return request.param


@pytest.mark.parametrize(
    "failure",
    [
        _html_answer(),
        ReadTimeout("read timed out"),
        BinanceRequestException("down"),
        _api_error(-1007, "Timeout waiting for response from backend server."),
        _api_error(-1006, "An unexpected response was received from the message bus."),
    ],
    ids=[
        "html page",
        "read timeout",
        "binance request error",
        "-1007 send status unknown",
        "-1006 execution status unknown",
    ],
)
def test_a_live_submission_with_no_readable_answer_is_outcome_unknown(
    venue: str, failure: Exception
) -> None:
    raw = Mock()
    _create(venue, raw).side_effect = failure
    client = _build(venue, raw, OrderSubmissionMode.LIVE)

    with pytest.raises(OrderOutcomeUnknownError) as unknown:
        client.place_order(_ORDER)

    assert unknown.value.client_order_id == _ID
    assert unknown.value.symbol == "BTCUSDT"
    assert "<" not in str(unknown.value)


def test_a_json_rejection_stays_a_rejection(venue: str) -> None:
    raw = Mock()
    _create(venue, raw).side_effect = _api_error(-2019, "Margin is insufficient")
    client = _build(venue, raw, OrderSubmissionMode.LIVE)

    with pytest.raises(OrderRejectedByExchangeError):
        client.place_order(_ORDER)


def test_a_validate_only_page_is_not_an_unknown_outcome(venue: str) -> None:
    """The test endpoint never creates an order, so nothing can be live."""
    raw = Mock()
    raw.futures_create_test_order.side_effect = _html_answer()
    raw.create_test_order.side_effect = _html_answer()
    client = _build(venue, raw, OrderSubmissionMode.VALIDATE_ONLY)

    with pytest.raises(OrderRejectedByExchangeError):
        client.place_order(_ORDER)


def test_find_order_reads_the_order_by_its_client_order_id(venue: str) -> None:
    raw = Mock()
    _get(venue, raw).return_value = _row()
    client = _build(venue, raw, OrderSubmissionMode.LIVE)

    found = client.find_order("BTCUSDT", _ID)

    assert found is not None
    assert found.client_order_id == _ID
    assert found.status is OrderStatus.FILLED
    assert _get(venue, raw).call_args.kwargs["origClientOrderId"] == _ID


def test_find_order_answers_none_when_the_exchange_has_no_such_order(
    venue: str,
) -> None:
    raw = Mock()
    _get(venue, raw).side_effect = _api_error(_UNKNOWN_ORDER, "Order does not exist.")
    # Futures asks the Algo Order API too, where a conditional order lives.
    raw.futures_get_algo_order.side_effect = _api_error(
        _UNKNOWN_ORDER, "Order does not exist."
    )
    client = _build(venue, raw, OrderSubmissionMode.LIVE)

    assert client.find_order("BTCUSDT", _ID) is None


def test_a_futures_stop_limit_is_found_through_the_algo_order_api() -> None:
    raw = Mock()
    raw.futures_get_order.side_effect = _api_error(
        _UNKNOWN_ORDER, "Order does not exist."
    )
    raw.futures_get_algo_order.return_value = {
        "clientAlgoId": _ID,
        "orderType": "STOP",
        "symbol": "BTCUSDT",
        "side": "BUY",
        "quantity": "0.002",
        "algoStatus": "NEW",
        "triggerPrice": "65000.00",
        "price": "65100.00",
        "timeInForce": "GTC",
        "createTime": 1_790_000_000_000,
    }
    client = _build("futures", raw, OrderSubmissionMode.LIVE)

    found = client.find_order("BTCUSDT", _ID)

    assert found is not None
    assert found.client_order_id == _ID
    assert raw.futures_get_algo_order.call_args.kwargs["clientAlgoId"] == _ID


@pytest.mark.parametrize(
    "failure", [_html_answer(), ReadTimeout("read timed out")], ids=["html", "timeout"]
)
def test_find_order_that_cannot_ask_is_outcome_unknown(
    venue: str, failure: Exception
) -> None:
    raw = Mock()
    _get(venue, raw).side_effect = failure
    client = _build(venue, raw, OrderSubmissionMode.LIVE)

    with pytest.raises(OrderOutcomeUnknownError):
        client.find_order("BTCUSDT", _ID)
