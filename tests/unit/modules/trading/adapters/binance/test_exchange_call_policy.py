"""`EPIC-035D` — the one retry policy below the gateway.

A read or a cancel that failed in transit is tried again after a growing, capped
wait; a call that is an order's submit is never tried again here, whatever failed
(its unknown outcome has its own resolution: the lookup by client order id).
A rate-limit answer is not waited out in the call: it closes the venue's gate for
the stated pause and ends the call with `RateLimitedApiException`, and while the
gate is closed no call of the venue sends anything. Time is the test's: a fake
clock and a recording sleep; nothing waits.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from binance.exceptions import BinanceAPIException
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.exchange_call_policy import (
    READ_RETRY_DELAYS_SECONDS,
    ExchangeCallPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.rate_limit_gate import (
    RateLimitGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.rate_limited_api_exception import (
    RateLimitedApiException,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.adapters.binance.exchange_answers import (
    html_page,
    rate_limited,
    refusal,
    reset,
    timeout,
)

_NOW_MS = 1_700_000_000_000


class _World:
    """A fake clock the sleeps move, and a call that fails as scripted."""

    def __init__(self, *failures: Exception, while_asleep: float = 0.0) -> None:
        self.at = 0.0
        #: Seconds another thread closes the gate for during each sleep.
        self._while_asleep = while_asleep
        self.sleeps: list[float] = []
        self.sent = 0
        self._failures = list(failures)
        self.gate = RateLimitGate(lambda: self.at)
        self.policy = ExchangeCallPolicy(
            self.gate, sleep=self._sleep, wall_seconds=lambda: _NOW_MS / 1000
        )

    def _sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.at += seconds
        if self._while_asleep:
            self.gate.block(self._while_asleep)

    def call(self) -> str:
        self.sent += 1
        if self._failures:
            raise self._failures.pop(0)
        return "answer"


def test_a_timeout_is_retried_and_the_answer_returned() -> None:
    world = _World(timeout())

    assert world.policy.run_read(world.call) == "answer"
    assert (world.sent, world.sleeps) == (2, [READ_RETRY_DELAYS_SECONDS[0]])


def test_the_wait_grows_and_is_capped_and_the_last_failure_is_raised() -> None:
    failures = [reset() for _ in range(len(READ_RETRY_DELAYS_SECONDS) + 1)]
    world = _World(*failures)

    with pytest.raises(type(failures[0])):
        world.policy.run_read(world.call)

    assert world.sent == len(READ_RETRY_DELAYS_SECONDS) + 1
    assert world.sleeps == list(READ_RETRY_DELAYS_SECONDS)
    assert world.sleeps == sorted(world.sleeps), "the wait only grows"
    assert max(world.sleeps) <= 10.0, "and is capped"


def test_a_gateway_page_is_retried() -> None:
    world = _World(html_page(503))
    assert world.policy.run_read(world.call) == "answer"
    assert world.sent == 2


def test_an_answer_the_exchange_gave_is_raised_at_once() -> None:
    answer = refusal(-2011, "Unknown order sent.")
    world = _World(answer)

    with pytest.raises(type(answer)) as raised:
        world.policy.run_read(world.call)

    assert raised.value is answer
    assert (world.sent, world.sleeps) == (1, [])


def test_a_submit_is_never_sent_twice_whatever_failed() -> None:
    world = _World(timeout(), timeout(), timeout())

    with pytest.raises(type(timeout())):
        world.policy.run_once(world.call)

    assert (world.sent, world.sleeps) == (1, [])


def test_a_429_closes_the_gate_for_the_stated_pause_and_ends_the_call() -> None:
    world = _World(rate_limited(retry_after="40"))

    with pytest.raises(RateLimitedApiException) as raised:
        world.policy.run_read(world.call)

    assert raised.value.retry_after == timedelta(seconds=40)
    assert raised.value.banned is False
    assert world.gate.remaining() == 40.0
    assert (world.sent, world.sleeps) == (1, []), "a rate limit is not waited out"


def test_while_the_gate_is_closed_nothing_is_sent_by_any_kind_of_call() -> None:
    world = _World(rate_limited(retry_after="40"))
    with pytest.raises(RateLimitedApiException):
        world.policy.run_read(world.call)
    world.at += 15

    for run in (world.policy.run_read, world.policy.run_once):
        with pytest.raises(RateLimitedApiException) as raised:
            run(world.call)
        assert raised.value.retry_after == timedelta(seconds=25)

    assert world.sent == 1


def test_the_gate_reopens_at_the_end_of_the_pause() -> None:
    world = _World(rate_limited(retry_after="40"))
    with pytest.raises(RateLimitedApiException):
        world.policy.run_read(world.call)

    world.at += 40

    assert world.policy.run_once(world.call) == "answer"
    assert world.sent == 2


def test_a_418_is_a_ban_for_its_window() -> None:
    world = _World(rate_limited(418, retry_after="600"))

    with pytest.raises(RateLimitedApiException) as raised:
        world.policy.run_once(world.call)

    assert raised.value.banned is True
    assert raised.value.retry_after == timedelta(seconds=600)
    assert world.gate.banned is True


def test_a_rate_limit_during_a_retry_stops_the_retrying() -> None:
    world = _World(timeout(), rate_limited(retry_after="30"))

    with pytest.raises(RateLimitedApiException):
        world.policy.run_read(world.call)

    assert (world.sent, len(world.sleeps)) == (2, 1)


def test_the_gate_closing_while_a_retry_waits_ends_the_retry_without_a_request() -> (
    None
):
    world = _World(timeout(), while_asleep=60.0)

    with pytest.raises(RateLimitedApiException):
        world.policy.run_read(world.call)

    assert world.sent == 1


def test_the_rate_limit_error_is_still_a_binance_exception_for_every_handler_of_one() -> (
    None
):
    """Around fifteen adapters turn a `BinanceAPIException` into their own result;
    a pause must reach them as one, with the 429 it stands for."""
    world = _World(rate_limited(retry_after="5"))

    with pytest.raises(BinanceAPIException) as raised:
        world.policy.run_once(world.call)

    assert (raised.value.status_code, raised.value.code) == (429, -1003)
    assert raised.value.response.headers["Retry-After"] == "5"


def test_the_original_failure_is_kept_as_the_cause() -> None:
    answer = rate_limited(retry_after="5")
    world = _World(answer)

    with pytest.raises(RateLimitedApiException) as raised:
        world.policy.run_once(world.call)

    assert raised.value.__cause__ is answer


def test_used_weight_near_the_limit_pauses_to_the_end_of_the_minute() -> None:
    world = _World()
    policy = ExchangeCallPolicy(
        world.gate,
        sleep=world.sleeps.append,
        weight_limit=1200,
        wall_seconds=lambda: 600.0 + 45.0,
    )

    policy.note_used_weight(1079)
    assert world.gate.remaining() == 0.0
    policy.note_used_weight(1080)

    assert world.gate.remaining() == pytest.approx(16.0), "15 s left of the minute, +1"


def test_a_weight_header_that_is_not_a_number_is_ignored() -> None:
    world = _World()
    world.policy.note_used_weight_header("many")
    world.policy.note_used_weight_header(None)
    assert world.gate.remaining() == 0.0
