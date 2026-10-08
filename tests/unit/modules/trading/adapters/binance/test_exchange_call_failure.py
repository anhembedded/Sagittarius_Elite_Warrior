"""`EPIC-035D` — which failures of an exchange call are worth another try.

One function says it for every adapter: a transport failure or a gateway's page
is `TRANSIENT`; HTTP 429 and the codes `-1003` / `-1015` are `RATE_LIMITED` with
the pause the exchange stated (`Retry-After`, or the instant a ban ends), else a
named default; HTTP 418 is `BANNED`. Anything the exchange answered with another
code is `OTHER`: it read the request and refused it, and asking again changes
nothing.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.exchange_call_failure import (
    DEFAULT_BAN_PAUSE_SECONDS,
    DEFAULT_ORDER_COUNT_PAUSE_SECONDS,
    DEFAULT_RATE_LIMIT_PAUSE_SECONDS,
    ExchangeFailure,
    FailureKind,
    classify_exchange_failure,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.adapters.binance.exchange_answers import (
    html_page,
    rate_limited,
    refusal,
    reset,
    timeout,
    unreadable,
)

_NOW_MS = 1_700_000_000_000


@pytest.mark.parametrize(
    "failure",
    [timeout(), reset(), unreadable(), html_page(502), html_page(503), html_page(504)],
)
def test_a_transport_failure_or_a_gateway_page_is_transient(
    failure: Exception,
) -> None:
    assert classify_exchange_failure(failure, _NOW_MS).kind is FailureKind.TRANSIENT


@pytest.mark.parametrize("code", [-1001, -1006, -1007])
def test_the_exchanges_own_busy_codes_are_transient(code: int) -> None:
    assert (
        classify_exchange_failure(refusal(code, status=503), _NOW_MS).kind
        is FailureKind.TRANSIENT
    )


@pytest.mark.parametrize("code", [-2011, -2013, -1013, -1021, -2010, -1102])
def test_an_answer_the_exchange_gave_is_never_retried(code: int) -> None:
    assert classify_exchange_failure(refusal(code), _NOW_MS) == ExchangeFailure(
        FailureKind.OTHER
    )


def test_retry_after_is_the_pause_the_exchange_asked_for() -> None:
    failure = classify_exchange_failure(rate_limited(retry_after="37"), _NOW_MS)
    assert failure == ExchangeFailure(FailureKind.RATE_LIMITED, 37.0)


def test_a_429_without_retry_after_gets_the_named_default() -> None:
    failure = classify_exchange_failure(rate_limited(), _NOW_MS)
    assert failure == ExchangeFailure(
        FailureKind.RATE_LIMITED, DEFAULT_RATE_LIMIT_PAUSE_SECONDS
    )


def test_too_many_new_orders_is_a_short_default_pause() -> None:
    failure = classify_exchange_failure(rate_limited(code=-1015), _NOW_MS)
    assert failure == ExchangeFailure(
        FailureKind.RATE_LIMITED, DEFAULT_ORDER_COUNT_PAUSE_SECONDS
    )


def test_a_429_page_with_no_json_is_still_rate_limited_and_honours_the_header() -> None:
    failure = classify_exchange_failure(html_page(429, retry_after="12"), _NOW_MS)
    assert failure == ExchangeFailure(FailureKind.RATE_LIMITED, 12.0)


def test_a_418_is_a_ban_for_the_stated_window() -> None:
    failure = classify_exchange_failure(rate_limited(418, retry_after="300"), _NOW_MS)
    assert failure == ExchangeFailure(FailureKind.BANNED, 300.0)


def test_a_418_without_retry_after_gets_the_minimum_ban_window() -> None:
    failure = classify_exchange_failure(rate_limited(418), _NOW_MS)
    assert failure == ExchangeFailure(FailureKind.BANNED, DEFAULT_BAN_PAUSE_SECONDS)


def test_a_ban_message_names_the_instant_it_ends() -> None:
    message = f"Way too many requests; IP banned until {_NOW_MS + 90_000}. Please use the websocket."
    failure = classify_exchange_failure(rate_limited(418, message=message), _NOW_MS)
    assert failure == ExchangeFailure(FailureKind.BANNED, 90.0)


def test_a_ban_that_already_ended_is_not_a_negative_pause() -> None:
    message = f"IP banned until {_NOW_MS - 5_000}."
    failure = classify_exchange_failure(rate_limited(418, message=message), _NOW_MS)
    assert failure.kind is FailureKind.BANNED
    assert failure.pause_seconds >= 1.0


@pytest.mark.parametrize("header", ["soon", "", "-4", "0"])
def test_a_retry_after_that_is_not_a_positive_number_falls_back_to_the_default(
    header: str,
) -> None:
    failure = classify_exchange_failure(rate_limited(retry_after=header), _NOW_MS)
    assert failure.pause_seconds == DEFAULT_RATE_LIMIT_PAUSE_SECONDS


def test_a_pause_is_capped_so_a_huge_header_cannot_park_a_bot_for_days() -> None:
    failure = classify_exchange_failure(
        rate_limited(418, retry_after=str(10**9)), _NOW_MS
    )
    assert failure.pause_seconds <= 3 * 24 * 3600
