"""`DeliveryResult` cannot say two things at once."""

from __future__ import annotations

from datetime import timedelta

import pytest
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.delivery_result import (
    DeliveryResult,
)


def test_a_sent_result_is_ok_and_carries_no_retry_or_reason() -> None:
    result = DeliveryResult.sent()

    assert (result.ok, result.retry_after, result.permanent, result.reason) == (
        True,
        None,
        False,
        "",
    )


def test_a_retry_later_result_names_when_and_why() -> None:
    result = DeliveryResult.retry_later(timedelta(seconds=2), "rate limited")

    assert result.ok is False
    assert result.retry_after == timedelta(seconds=2)
    assert result.permanent is False
    assert result.reason == "rate limited"


def test_a_failed_result_is_transient_and_a_refused_one_permanent() -> None:
    assert DeliveryResult.failed("timeout").permanent is False
    assert DeliveryResult.failed("timeout").retry_after is None
    assert DeliveryResult.refused("webhook deleted").permanent is True


def test_a_failure_must_say_why() -> None:
    with pytest.raises(ValueError, match="reason"):
        DeliveryResult.failed("")


def test_a_retry_after_cannot_be_negative_or_zero() -> None:
    with pytest.raises(ValueError, match="retry_after"):
        DeliveryResult.retry_later(timedelta(0), "x")


def test_an_ok_result_cannot_also_be_a_failure() -> None:
    with pytest.raises(ValueError, match="ok"):
        DeliveryResult(ok=True, permanent=True)
    with pytest.raises(ValueError, match="ok"):
        DeliveryResult(ok=True, retry_after=timedelta(seconds=1))
    with pytest.raises(ValueError, match="permanent"):
        DeliveryResult(
            ok=False, permanent=True, retry_after=timedelta(seconds=1), reason="x"
        )
