"""`EPIC-036G` — what each Discord answer means for the worker; a 429's wait is
Discord's own, never shortened."""

from __future__ import annotations

from datetime import timedelta

import pytest
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.discord_answer import (
    DEFAULT_RETRY_AFTER,
    result_of,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.retry_wait import (
    MAX_RETRY_AFTER,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_webhook_transport import (
    WebhookResponse,
)


@pytest.mark.parametrize("status", [200, 204])
def test_a_2xx_is_sent(status: int) -> None:
    assert result_of(WebhookResponse(status)).ok


def test_a_429_answers_retry_later_with_discords_wait() -> None:
    result = result_of(
        WebhookResponse(429, {}, b'{"retry_after": 1.5, "global": false}')
    )

    assert not result.ok and not result.permanent
    assert result.retry_after == timedelta(seconds=1.5)
    assert "429" in result.reason


def test_retry_after_from_the_header_when_the_body_has_none() -> None:
    result = result_of(WebhookResponse(429, {"Retry-After": "3"}, b""))

    assert result.retry_after == timedelta(seconds=3)


def test_the_body_wins_over_the_header() -> None:
    result = result_of(
        WebhookResponse(429, {"Retry-After": "3"}, b'{"retry_after": 7}')
    )

    assert result.retry_after == timedelta(seconds=7)


def test_a_fraction_of_a_millisecond_is_rounded_up_never_down() -> None:
    result = result_of(WebhookResponse(429, {}, b'{"retry_after": 0.0001}'))

    assert result.retry_after == timedelta(milliseconds=1)


@pytest.mark.parametrize(
    "body, header",
    [
        (b"", ""),
        (b"<html>busy</html>", ""),
        (b'{"retry_after": -1}', "soon"),
        (b"[]", ""),
    ],
)
def test_a_429_that_names_no_usable_wait_waits_the_default(
    body: bytes, header: str
) -> None:
    headers = {"Retry-After": header} if header else {}

    assert (
        result_of(WebhookResponse(429, headers, body)).retry_after
        == DEFAULT_RETRY_AFTER
    )


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_a_client_error_is_a_permanent_refusal(status: int) -> None:
    result = result_of(WebhookResponse(status))

    assert result.permanent
    assert str(status) in result.reason


@pytest.mark.parametrize("status", [500, 502, 503])
def test_a_server_error_is_a_failure_that_may_pass(status: int) -> None:
    result = result_of(WebhookResponse(status))

    assert not result.ok and not result.permanent and result.retry_after is None


@pytest.mark.parametrize(
    "body",
    [b'{"retry_after": 1e14}', b'{"retry_after": 3e11}'],
    ids=["1e14", "3e11"],
)
def test_a_wait_no_alert_outlives_is_capped_not_an_overflow(body: bytes) -> None:
    result = result_of(WebhookResponse(429, {}, body))

    assert result.retry_after == MAX_RETRY_AFTER


def test_a_huge_retry_after_header_is_capped_too() -> None:
    assert (
        result_of(WebhookResponse(429, {"Retry-After": "1e20"})).retry_after
        == MAX_RETRY_AFTER
    )


def test_an_integer_too_large_for_a_float_is_capped_not_an_overflow() -> None:
    body = b'{"retry_after": 1' + b"0" * 400 + b"}"

    assert result_of(WebhookResponse(429, {}, body)).retry_after == MAX_RETRY_AFTER
