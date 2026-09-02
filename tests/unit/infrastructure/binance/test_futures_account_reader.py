"""`EPIC-021D` — `FuturesAccountReader`: the classification logic that
turns a raw Binance error/payload into a named `ConnectionFailureKind`.
Uses `Mock` for the SDK-facing boundary (`ExchangeSessionFactory`/its
`Client`) and the credentials provider — this file's whole job is proving
the classification, not re-testing `EnvFirstCredentialsProvider` or
`ExchangeSessionFactory` themselves."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import Mock

import pytest
from binance.exceptions import BinanceAPIException, BinanceRequestException
from requests.exceptions import ConnectionError as RequestsConnectionError
from Sagittarius_Elite_Warrior.src.application.ports.i_exchange_credentials_provider import (
    CredentialsSource,
    ResolvedCredentials,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.exchange_connection_status import (
    ConnectionFailureKind,
    MarginType,
    PositionMode,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.infrastructure.binance.futures_account_reader import (
    FuturesAccountReader,
)

_CREDENTIALS = ExchangeCredentials(api_key="key", api_secret="secret")


def _binance_api_exception(code: int) -> BinanceAPIException:
    exc = BinanceAPIException.__new__(BinanceAPIException)
    exc.code = code
    exc.message = f"binance error {code}"
    exc.status_code = 400
    exc.response = None
    exc.request = None
    return exc


def _reader(raw_client: Mock, credentials: ExchangeCredentials | None = _CREDENTIALS):
    session_factory = Mock()
    session_factory.create_trading_client.return_value = raw_client
    credentials_provider = Mock()
    source = CredentialsSource.NONE if credentials is None else CredentialsSource.FILE
    credentials_provider.resolve.return_value = ResolvedCredentials(credentials, source)
    return FuturesAccountReader(session_factory, credentials_provider)


def _account_payload(
    usdt_balance: str = "15000.00000000",
    positions: list[dict] | None = None,
) -> dict:
    return {
        "assets": [{"asset": "USDT", "walletBalance": usdt_balance}],
        "positions": positions or [],
    }


def _happy_client(
    account_payload: dict | None = None, dual_side_position: bool = False
) -> Mock:
    client = Mock()
    client.futures_ping.return_value = {}
    client.futures_time.return_value = {"serverTime": 0}
    client.futures_account.return_value = account_payload or _account_payload()
    client.futures_get_position_mode.return_value = {
        "dualSidePosition": dual_side_position
    }
    return client


# ---------------------------------------------------------------------------
# Not configured — no network call attempted
# ---------------------------------------------------------------------------


def test_no_credentials_returns_not_configured_without_touching_the_network():
    reader = _reader(Mock(), credentials=None)

    status = reader.check_connection()

    assert status.venue is TradingVenue.FUTURES_TESTNET
    assert status.reachable is False
    assert status.failure is ConnectionFailureKind.NOT_CONFIGURED


# ---------------------------------------------------------------------------
# Error classification
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "code,expected_kind",
    [
        (-1021, ConnectionFailureKind.CLOCK_SKEW),
        (-1022, ConnectionFailureKind.BAD_SIGNATURE),
        (-2015, ConnectionFailureKind.KEY_EXPIRED),
        (-9999, ConnectionFailureKind.NETWORK),  # unrecognized code -> fallback
    ],
)
def test_a_binance_api_error_on_ping_classifies_correctly(code, expected_kind):
    client = Mock()
    client.futures_ping.side_effect = _binance_api_exception(code)
    reader = _reader(client)

    status = reader.check_connection()

    assert status.reachable is False
    assert status.failure is expected_kind


def test_a_network_level_error_on_ping_classifies_as_network():
    client = Mock()
    client.futures_ping.side_effect = RequestsConnectionError("no route")
    reader = _reader(client)

    status = reader.check_connection()

    assert status.failure is ConnectionFailureKind.NETWORK


def test_a_binance_request_exception_classifies_as_network():
    client = Mock()
    client.futures_ping.side_effect = BinanceRequestException("invalid json")
    reader = _reader(client)

    status = reader.check_connection()

    assert status.failure is ConnectionFailureKind.NETWORK


def test_a_network_failure_during_client_construction_itself_classifies_as_network():
    """Regression: `Client(...)`'s own constructor pings on construction by
    default (`ping=True`, `BUG-045`'s trigger) — a real run against this
    sandbox's blocked egress surfaced an uncaught `ProxyError` here before
    this test/fix existed, because the try block only wrapped calls made
    *after* construction, not construction itself."""
    session_factory = Mock()
    session_factory.create_trading_client.side_effect = RequestsConnectionError(
        "blocked"
    )
    credentials_provider = Mock()
    credentials_provider.resolve.return_value = ResolvedCredentials(
        _CREDENTIALS, CredentialsSource.FILE
    )
    reader = FuturesAccountReader(session_factory, credentials_provider)

    status = reader.check_connection()

    assert status.reachable is False
    assert status.failure is ConnectionFailureKind.NETWORK


def test_a_failure_on_the_account_call_still_reports_the_clock_skew_already_measured():
    """Losing already-measured data on a later failure would make the user
    re-diagnose from scratch — `-1021` on `futures_account` after a
    successful `futures_time` should still show the skew that was
    measured."""
    client = Mock()
    client.futures_ping.return_value = {}
    client.futures_time.return_value = {"serverTime": 0}
    client.futures_account.side_effect = _binance_api_exception(-1022)
    reader = _reader(client)

    status = reader.check_connection()

    assert status.failure is ConnectionFailureKind.BAD_SIGNATURE
    assert status.server_time_skew_ms is not None


def test_a_failure_on_position_mode_still_reports_balance_and_positions():
    client = _happy_client()
    client.futures_get_position_mode.side_effect = _binance_api_exception(-1021)
    reader = _reader(client)

    status = reader.check_connection()

    assert status.failure is ConnectionFailureKind.CLOCK_SKEW
    assert status.usdt_balance == Decimal("15000.00000000")


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------


def test_a_fully_successful_check_reports_every_field():
    client = _happy_client(
        account_payload=_account_payload(
            positions=[
                {"positionAmt": "0.5", "isolated": False},
                {"positionAmt": "0", "isolated": True},
            ]
        )
    )
    reader = _reader(client)

    status = reader.check_connection()

    assert status.venue is TradingVenue.FUTURES_TESTNET
    assert status.reachable is True
    assert status.failure is None
    assert status.usdt_balance == Decimal("15000.00000000")
    assert status.position_mode is PositionMode.ONE_WAY
    assert status.margin_type is MarginType.CROSSED
    assert status.open_position_count == 1  # the 0-amount position is excluded


def test_hedge_mode_is_a_named_failure_not_a_silent_success():
    """`EPIC-021D` §2.3 — the whole point of this task's added
    `HEDGE_MODE_UNSUPPORTED` kind."""
    client = _happy_client(dual_side_position=True)
    reader = _reader(client)

    status = reader.check_connection()

    assert status.reachable is True
    assert status.position_mode is PositionMode.HEDGE
    assert status.failure is ConnectionFailureKind.HEDGE_MODE_UNSUPPORTED


def test_clock_skew_is_positive_when_the_local_clock_is_ahead():
    client = Mock()
    client.futures_ping.return_value = {}
    far_past_server_time_ms = 0
    client.futures_time.return_value = {"serverTime": far_past_server_time_ms}
    client.futures_account.return_value = _account_payload()
    client.futures_get_position_mode.return_value = {"dualSidePosition": False}
    reader = _reader(client)

    status = reader.check_connection()

    assert status.server_time_skew_ms is not None
    assert status.server_time_skew_ms > 0


def test_no_usdt_asset_in_the_account_payload_reports_none_not_zero():
    client = _happy_client(account_payload={"assets": [], "positions": []})
    reader = _reader(client)

    status = reader.check_connection()

    assert status.usdt_balance is None


def test_no_open_positions_reports_none_margin_type_not_a_guess():
    client = _happy_client(account_payload=_account_payload(positions=[]))
    reader = _reader(client)

    status = reader.check_connection()

    assert status.margin_type is None
    assert status.open_position_count == 0
