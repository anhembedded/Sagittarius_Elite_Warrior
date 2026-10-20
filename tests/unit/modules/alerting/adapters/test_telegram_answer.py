"""`EPIC-036C1` - what Telegram's answer to `sendMessage` means for the worker."""

from __future__ import annotations

from datetime import timedelta

import pytest
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.telegram_answer import (
    DEFAULT_RETRY_AFTER,
    result_of,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_webhook_transport import (
    WebhookResponse,
)


def test_an_accepted_message_is_sent() -> None:
    assert result_of(WebhookResponse(200, {}, b'{"ok": true}')).ok


def test_a_429_waits_the_time_telegram_names_in_its_parameters() -> None:
    body = b'{"ok": false, "error_code": 429, "parameters": {"retry_after": 3600}}'

    result = result_of(WebhookResponse(429, {}, body))

    assert result.retry_after == timedelta(hours=1)
    assert not result.permanent


def test_a_429_falls_back_to_the_header_and_then_to_a_default() -> None:
    assert result_of(
        WebhookResponse(429, {"Retry-After": "7"}, b"not json")
    ).retry_after == timedelta(seconds=7)
    assert result_of(WebhookResponse(429)).retry_after == DEFAULT_RETRY_AFTER


@pytest.mark.parametrize("bad", ["0", "-3", "nan", "inf", "soon"])
def test_a_wait_that_is_not_a_positive_number_is_not_believed(bad: str) -> None:
    body = f'{{"parameters": {{"retry_after": "{bad}"}}}}'.encode()

    assert result_of(WebhookResponse(429, {}, body)).retry_after == DEFAULT_RETRY_AFTER


def test_chat_not_found_becomes_guidance_and_is_permanent() -> None:
    body = b'{"ok": false, "error_code": 400, "description": "Bad Request: chat not found"}'

    result = result_of(WebhookResponse(400, {}, body))

    assert result.permanent
    assert "press Start" in result.reason
    assert "chat id" in result.reason


def test_a_bot_that_may_not_write_to_the_chat_becomes_guidance() -> None:
    body = b'{"ok": false, "error_code": 403, "description": "Forbidden: bot was blocked by the user"}'

    result = result_of(WebhookResponse(403, {}, body))

    assert result.permanent
    assert "press Start" in result.reason


def test_a_rejected_token_says_so() -> None:
    result = result_of(WebhookResponse(401, {}, b'{"ok": false, "error_code": 401}'))

    assert result.permanent
    assert "token" in result.reason


def test_any_other_client_error_is_permanent_and_names_only_the_status() -> None:
    result = result_of(
        WebhookResponse(400, {}, b'{"description": "Bad Request: text is empty"}')
    )

    assert result.permanent
    assert "400" in result.reason
    assert "text is empty" not in result.reason


def test_a_server_error_is_retried() -> None:
    result = result_of(WebhookResponse(502, {}, b"<html>bad gateway</html>"))

    assert not result.ok
    assert not result.permanent
    assert result.retry_after is None
