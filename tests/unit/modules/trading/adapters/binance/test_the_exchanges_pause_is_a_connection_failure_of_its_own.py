"""`BUG-216` - the connection check names the exchange's pause, and does not read what never changes.

@details The owner's log, 2026-10-15: `Futures Testnet connection check failed with an unclassified
exception: RateLimitedApiException: APIError(code=-1003)`, an ERROR every five seconds, and an order
gate that read the pause as "the connection is not ready". Here: the pause is `RATE_LIMITED` with
the time the exchange asked for, whichever way it reaches the check (the app's own gate, a raw
`-1003`/`-1015`, an HTTP 429 or a 418 ban), and it is not logged as a failure; an unknown code is
still `NETWORK` and still an ERROR (`BUG-137`). And the position mode, 30 weight of a check's 37,
is read once a minute, never when it is Hedge, never when its read failed.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from unittest.mock import Mock

import pytest
from binance.exceptions import BinanceAPIException
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.connection_failure import (
    classify_connection_failure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_account_reader import (
    POSITION_MODE_TTL_SECONDS,
    FuturesAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.rate_limited_api_exception import (
    RateLimitedApiException,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
    ExchangeConnectionStatus,
    PositionMode,
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

_LABEL = "Futures Testnet"


def _answer(code: int, status: int, retry_after: str | None = None) -> Exception:
    exc = BinanceAPIException.__new__(BinanceAPIException)
    exc.code, exc.message, exc.status_code, exc.request = (
        code,
        f"binance error {code}",
        status,
        None,
    )
    exc.response = Mock(headers={"Retry-After": retry_after} if retry_after else {})
    return exc


@pytest.mark.parametrize(
    "exc",
    [
        RateLimitedApiException(
            timedelta(seconds=32), banned=False, note="no request is sent"
        ),
        _answer(-1003, 429, "30"),
        _answer(-1003, 400),
        _answer(-1015, 400),
        _answer(-1000, 429, "30"),
        _answer(-1003, 418, "120"),
    ],
    ids=["own gate", "429 -1003", "-1003 alone", "-1015", "429 alone", "418 ban"],
)
def test_every_way_the_exchange_asks_for_a_pause_is_one_kind(exc: Exception) -> None:
    assert (
        classify_connection_failure(exc, _LABEL) is ConnectionFailureKind.RATE_LIMITED
    )


def test_a_pause_is_not_logged_as_a_failure_and_an_unknown_code_still_is(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="App.TradingAdapter")

    classify_connection_failure(_answer(-1003, 429, "30"), _LABEL)
    quiet = [r for r in caplog.records if r.levelno >= logging.INFO]
    classify_connection_failure(_answer(-9999, 400), _LABEL)
    loud = [r for r in caplog.records if r.levelno >= logging.ERROR]

    assert quiet == [], (
        "a poll meets the pause every few seconds; the policy told it once"
    )
    assert len(loud) == 1
    assert "unclassified exception" in loud[0].getMessage()


class _Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _reader(client: Mock, clock: _Clock) -> FuturesAccountReader:
    factory = Mock()
    factory.create_trading_client.return_value = client
    provider = Mock()
    provider.resolve.return_value = ResolvedCredentials(
        ExchangeCredentials(api_key="k", api_secret="s"), CredentialsSource.FILE
    )
    return FuturesAccountReader(factory, provider, clock)


def _client(*, hedge: bool = False) -> Mock:
    client = Mock()
    client.futures_ping.return_value = {}
    client.futures_time.return_value = {"serverTime": 0}
    client.futures_account.return_value = {
        "assets": [{"asset": "USDT", "walletBalance": "100"}],
        "positions": [],
    }
    client.futures_get_position_mode.return_value = {"dualSidePosition": hedge}
    client.futures_get_multi_assets_mode.return_value = {"multiAssetsMargin": False}
    return client


def test_the_check_reports_the_pause_with_the_time_the_exchange_asked_for() -> None:
    client = _client()
    client.futures_account.side_effect = _answer(-1003, 429, "45")

    status = _reader(client, _Clock()).check_connection()

    assert status.failure is ConnectionFailureKind.RATE_LIMITED
    assert status.retry_after == timedelta(seconds=45)
    assert status.banned is False
    assert status.reachable is False


def test_a_ban_is_a_pause_that_says_it_is_one() -> None:
    client = _client()
    client.futures_ping.side_effect = _answer(-1003, 418, "120")

    status = _reader(client, _Clock()).check_connection()

    assert status.failure is ConnectionFailureKind.RATE_LIMITED
    assert status.retry_after == timedelta(seconds=120)
    assert status.banned is True


def test_the_position_mode_is_read_once_in_a_minute_not_at_every_check() -> None:
    clock = _Clock()
    client = _client()
    reader = _reader(client, clock)

    first = reader.check_connection()
    clock.now += POSITION_MODE_TTL_SECONDS - 1
    second = reader.check_connection()

    assert client.futures_get_position_mode.call_count == 1
    assert first.position_mode is second.position_mode is PositionMode.ONE_WAY
    assert client.futures_account.call_count == 2, "the balances are read every time"

    clock.now += 1
    reader.check_connection()

    assert client.futures_get_position_mode.call_count == 2, "a minute is the limit"


def test_a_hedge_mode_is_never_kept_so_the_switch_back_shows_at_once() -> None:
    clock = _Clock()
    client = _client(hedge=True)
    reader = _reader(client, clock)

    hedged = reader.check_connection()
    client.futures_get_position_mode.return_value = {"dualSidePosition": False}
    back = reader.check_connection()

    assert hedged.failure is ConnectionFailureKind.HEDGE_MODE_UNSUPPORTED
    assert back.failure is None
    assert back.position_mode is PositionMode.ONE_WAY
    assert client.futures_get_position_mode.call_count == 2


def test_a_failed_position_mode_read_is_never_kept() -> None:
    clock = _Clock()
    client = _client()
    reader = _reader(client, clock)
    reader.check_connection()
    clock.now += POSITION_MODE_TTL_SECONDS
    client.futures_get_position_mode.side_effect = _answer(-1003, 429, "10")

    failed = reader.check_connection()
    client.futures_get_position_mode.side_effect = None
    again = reader.check_connection()

    assert failed.failure is ConnectionFailureKind.RATE_LIMITED
    assert again.failure is None
    assert client.futures_get_position_mode.call_count == 3


def test_a_status_that_is_rate_limited_must_say_for_how_long() -> None:
    """An invalid state is unrepresentable (`code/errors.md` #8), so a gate never has to
    invent a pause to wait."""
    with pytest.raises(ValueError, match="names its pause"):
        ExchangeConnectionStatus(
            venue=TradingVenue.FUTURES_TESTNET,
            reachable=False,
            failure=ConnectionFailureKind.RATE_LIMITED,
            server_time_skew_ms=None,
            usdt_balance=None,
            position_mode=None,
            margin_type=None,
            open_position_count=None,
        )
