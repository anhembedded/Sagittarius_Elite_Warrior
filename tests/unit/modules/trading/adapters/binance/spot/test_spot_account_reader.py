"""`EPIC-027H` — `SpotAccountReader`: the classification logic that turns a
raw Binance error/payload into a named `ConnectionFailureKind`, plus the
holdings/equity computation unique to Spot. Uses `Mock` for the SDK-facing
boundary (`ISpotSessionFactory`/its client) and the credentials provider —
this file's whole job is proving the classification and arithmetic, not
re-testing `EnvFirstCredentialsProvider` or `SpotSessionFactory` themselves
(same scope split `test_futures_account_reader.py` already uses)."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import Mock

import pytest
from binance.exceptions import BinanceAPIException, BinanceRequestException
from requests.exceptions import ConnectionError as RequestsConnectionError
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_account_reader import (
    SpotAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
    ResolvedCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
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
    session_factory.create_account_client.return_value = raw_client
    credentials_provider = Mock()
    source = CredentialsSource.NONE if credentials is None else CredentialsSource.FILE
    credentials_provider.resolve.return_value = ResolvedCredentials(credentials, source)
    return SpotAccountReader(session_factory, credentials_provider)


def _account_payload(balances: list[dict] | None = None) -> dict:
    return {
        "balances": (
            balances
            if balances is not None
            else [{"asset": "USDT", "free": "10000.00000000", "locked": "0"}]
        )
    }


def _happy_client(account_payload: dict | None = None) -> Mock:
    client = Mock()
    client.ping.return_value = {}
    client.get_server_time.return_value = {"serverTime": 0}
    client.get_account.return_value = account_payload or _account_payload()
    client.get_symbol_ticker.return_value = {"price": "50000.00"}
    return client


# --- Not configured — no network call attempted -----------------------------


def test_no_credentials_returns_not_configured_without_touching_the_network():
    reader = _reader(Mock(), credentials=None)
    status = reader.check_connection()
    assert status.venue is TradingVenue.SPOT_TESTNET
    assert status.reachable is False
    assert status.failure is ConnectionFailureKind.NOT_CONFIGURED


# --- Error classification ----------------------------------------------------


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
    client.ping.side_effect = _binance_api_exception(code)
    reader = _reader(client)
    status = reader.check_connection()
    assert status.reachable is False
    assert status.failure is expected_kind


def test_a_network_level_error_on_ping_classifies_as_network():
    client = Mock()
    client.ping.side_effect = RequestsConnectionError("no route")
    reader = _reader(client)
    status = reader.check_connection()
    assert status.failure is ConnectionFailureKind.NETWORK


def test_a_binance_request_exception_classifies_as_network():
    client = Mock()
    client.ping.side_effect = BinanceRequestException("invalid json")
    reader = _reader(client)
    status = reader.check_connection()
    assert status.failure is ConnectionFailureKind.NETWORK


def test_a_network_failure_during_client_construction_itself_classifies_as_network():
    """Regression shape (`BUG-045`, mirrored from `FuturesAccountReader`'s
    own test): `Client(...)` pings on construction by default — the try
    block must wrap construction itself, not only calls made after it."""
    session_factory = Mock()
    session_factory.create_account_client.side_effect = RequestsConnectionError(
        "blocked"
    )
    credentials_provider = Mock()
    credentials_provider.resolve.return_value = ResolvedCredentials(
        _CREDENTIALS, CredentialsSource.FILE
    )
    reader = SpotAccountReader(session_factory, credentials_provider)
    status = reader.check_connection()
    assert status.reachable is False
    assert status.failure is ConnectionFailureKind.NETWORK


def test_a_failure_on_the_account_call_still_reports_the_clock_skew_already_measured():
    client = Mock()
    client.ping.return_value = {}
    client.get_server_time.return_value = {"serverTime": 0}
    client.get_account.side_effect = _binance_api_exception(-1022)
    reader = _reader(client)
    status = reader.check_connection()
    assert status.failure is ConnectionFailureKind.BAD_SIGNATURE
    assert status.server_time_skew_ms is not None


# --- Success path -------------------------------------------------------------


def test_a_fully_successful_check_reports_the_quote_balance_and_holdings():
    client = _happy_client(
        account_payload=_account_payload(
            balances=[
                {"asset": "USDT", "free": "10000.00000000", "locked": "0"},
                {"asset": "BTC", "free": "0.5", "locked": "0"},
            ]
        )
    )
    reader = _reader(client)
    status = reader.check_connection()
    assert status.venue is TradingVenue.SPOT_TESTNET
    assert status.reachable is True
    assert status.failure is None
    assert status.usdt_balance == Decimal("10000.00000000")
    assert status.position_mode is None
    assert status.margin_type is None
    assert {h.asset for h in status.holdings} == {"USDT", "BTC"}


def test_no_usdt_balance_reports_zero_not_none():
    """Unlike Futures' own `usdt_balance` (`None` when the asset is
    missing), Spot's quote balance is meaningful even at zero — "no USDT"
    is a real, common account state, not "never learned"."""
    client = _happy_client(account_payload=_account_payload(balances=[]))
    reader = _reader(client)
    status = reader.check_connection()
    assert status.usdt_balance == Decimal(0)
    assert status.holdings == ()


def test_a_zero_balance_asset_is_not_reported_as_a_holding():
    client = _happy_client(
        account_payload=_account_payload(
            balances=[
                {"asset": "USDT", "free": "10000.00000000", "locked": "0"},
                {"asset": "BNB", "free": "0", "locked": "0"},
            ]
        )
    )
    reader = _reader(client)
    status = reader.check_connection()
    assert {h.asset for h in status.holdings} == {"USDT"}


def test_free_plus_locked_below_dust_threshold_is_flagged_as_dust():
    client = _happy_client(
        account_payload=_account_payload(
            balances=[
                {"asset": "USDT", "free": "10000.00000000", "locked": "0"},
                {"asset": "BNB", "free": "0.000000005", "locked": "0"},
            ]
        )
    )
    reader = _reader(client)
    status = reader.check_connection()
    bnb_holding = next(h for h in status.holdings if h.asset == "BNB")
    assert bnb_holding.is_dust is True


# --- Equity --------------------------------------------------------------


def test_equity_is_quote_balance_plus_holdings_priced_at_the_ticker():
    client = _happy_client(
        account_payload=_account_payload(
            balances=[
                {"asset": "USDT", "free": "10000.00000000", "locked": "0"},
                {"asset": "BTC", "free": "0.5", "locked": "0"},
            ]
        )
    )
    client.get_symbol_ticker.return_value = {"price": "50000.00"}
    reader = _reader(client)
    status = reader.check_connection()
    assert status.equity == Decimal("35000.00000000")
    client.get_symbol_ticker.assert_called_once_with(symbol="BTCUSDT")


def test_equity_excludes_dust_holdings_from_pricing():
    client = _happy_client(
        account_payload=_account_payload(
            balances=[
                {"asset": "USDT", "free": "10000.00000000", "locked": "0"},
                {"asset": "BNB", "free": "0.000000005", "locked": "0"},
            ]
        )
    )
    reader = _reader(client)
    status = reader.check_connection()
    assert status.equity == Decimal("10000.00000000")
    client.get_symbol_ticker.assert_not_called()


def test_equity_is_none_not_a_partial_sum_when_a_holding_cannot_be_priced():
    """Mutation-verify companion — if `_compute_equity` ever "helpfully"
    summed only the priceable holdings, this would go green for the wrong
    reason (`equity == quote_balance` by coincidence). Asserting `is None`
    keeps that failure mode red."""
    client = _happy_client(
        account_payload=_account_payload(
            balances=[
                {"asset": "USDT", "free": "10000.00000000", "locked": "0"},
                {"asset": "SHIB", "free": "1000000", "locked": "0"},
            ]
        )
    )
    client.get_symbol_ticker.side_effect = _binance_api_exception(-1121)
    reader = _reader(client)
    status = reader.check_connection()
    assert status.equity is None


def test_the_unpriceable_holding_warning_is_logged_once_not_every_poll(caplog):
    """`BUG-139` — the live UI polls `check_connection()` every few seconds
    (`HoldingsRefreshService`); a holding with no real market (a
    Testnet-only junk asset, or a genuinely untradeable one) must not spam
    an identical WARNING on every single poll forever. The equity result
    itself is unchanged (still `None` on every call — never a guessed
    partial sum); only the *log line* is deduplicated per asset."""
    client = _happy_client(
        account_payload=_account_payload(
            balances=[
                {"asset": "USDT", "free": "10000.00000000", "locked": "0"},
                {"asset": "SHIB", "free": "1000000", "locked": "0"},
            ]
        )
    )
    client.get_symbol_ticker.side_effect = _binance_api_exception(-1121)
    reader = _reader(client)

    with caplog.at_level("WARNING"):
        first = reader.check_connection()
        second = reader.check_connection()
        third = reader.check_connection()

    assert first.equity is None
    assert second.equity is None
    assert third.equity is None
    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(warnings) == 1
    assert "SHIB" in warnings[0].message


def test_equity_is_none_when_the_ticker_payload_is_malformed():
    client = _happy_client(
        account_payload=_account_payload(
            balances=[
                {"asset": "USDT", "free": "10000.00000000", "locked": "0"},
                {"asset": "BTC", "free": "0.5", "locked": "0"},
            ]
        )
    )
    client.get_symbol_ticker.return_value = {}
    reader = _reader(client)
    status = reader.check_connection()
    assert status.equity is None
