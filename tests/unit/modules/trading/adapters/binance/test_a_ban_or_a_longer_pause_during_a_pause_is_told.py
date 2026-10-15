"""`BUG-217` (review of PR #531) - a pause that escalates while one runs is told again, with its new end.

@details A burst has several answers in flight, so a soft pause (the app's own limit) can be
followed by a 429 with a longer `Retry-After`, or by a 418 ban. Telling only the pause that
begins from an open gate left the log with a 31 s soft pause and a "pause is over" ten minutes
later; an IP ban was invisible above DEBUG. The rule: a pause is told when it begins, when it
moves the announced end later, and when it turns the running pause into a ban; never twice for
the same end.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.exchange_call_policy import (
    ExchangeCallPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.rate_limit_gate import (
    RateLimitGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.rate_limited_api_exception import (
    RateLimitedApiException,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.adapters.binance.exchange_answers import (
    rate_limited,
)

_WALL = 645.0  # 45 s into a minute: a soft pause runs 16 s


def _policy() -> tuple[ExchangeCallPolicy, RateLimitGate]:
    gate = RateLimitGate(lambda: 0.0)
    return ExchangeCallPolicy(gate, weight_limit=1200, wall_seconds=lambda: _WALL), gate


def _refuse_with(
    policy: ExchangeCallPolicy,
    answer: Exception,
    *,
    while_in_flight: Callable[[], None] = lambda: None,
) -> None:
    """A request answered with `answer`; `while_in_flight` is what happened to the venue's
    gate between its sending and its answer (a burst has several requests in flight)."""

    def call() -> str:
        while_in_flight()
        raise answer

    with pytest.raises(RateLimitedApiException):
        policy.run_read(call)


def _told(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]


def test_a_ban_during_a_soft_pause_is_told_with_the_end_of_the_ban(
    caplog: pytest.LogCaptureFixture,
) -> None:
    policy, gate = _policy()
    caplog.set_level(logging.DEBUG, logger="App.TradingAdapter")

    _refuse_with(
        policy,
        rate_limited(418, retry_after="600"),
        while_in_flight=lambda: policy.note_used_weight(900),
    )

    told = _told(caplog)
    assert len(told) == 2, told
    assert "[rate-limit-soft]" in told[0]
    assert "[rate-limit-ban]" in told[1]
    ends = time.strftime("%H:%M:%S", time.localtime(_WALL + 600))
    assert f"until {ends}" in told[1], "the ban's end, not the soft pause's"
    assert gate.banned


def test_a_longer_429_during_a_short_pause_moves_the_announced_end(
    caplog: pytest.LogCaptureFixture,
) -> None:
    policy, _ = _policy()
    caplog.set_level(logging.DEBUG, logger="App.TradingAdapter")

    _refuse_with(
        policy,
        rate_limited(429, retry_after="300"),
        while_in_flight=lambda: _refuse_with(
            policy, rate_limited(429, code=-1015, retry_after="10")
        ),
    )

    told = _told(caplog)
    assert len(told) == 2, told
    ends = time.strftime("%H:%M:%S", time.localtime(_WALL + 300))
    assert f"until {ends}" in told[1]


def test_a_shorter_or_equal_pause_inside_a_pause_is_not_told_again(
    caplog: pytest.LogCaptureFixture,
) -> None:
    policy, _ = _policy()
    caplog.set_level(logging.DEBUG, logger="App.TradingAdapter")

    _refuse_with(policy, rate_limited(429, retry_after="60"))
    _refuse_with(policy, rate_limited(429, retry_after="60"))  # same end
    policy.note_used_weight(900)  # the minute ends in 16 s: shorter
    policy.note_used_weight(950)

    assert len(_told(caplog)) == 1


def test_an_ended_pause_is_told_again_when_the_next_one_begins(
    caplog: pytest.LogCaptureFixture,
) -> None:
    gate_now = [0.0]
    gate = RateLimitGate(lambda: gate_now[0])
    policy = ExchangeCallPolicy(gate, weight_limit=1200, wall_seconds=lambda: _WALL)
    caplog.set_level(logging.DEBUG, logger="App.TradingAdapter")

    _refuse_with(policy, rate_limited(429, retry_after="10"))
    gate_now[0] += 11.0
    assert policy.run_read(lambda: "answer") == "answer"
    _refuse_with(policy, rate_limited(429, retry_after="10"))

    kinds = [m for m in _told(caplog) if "[rate-limit-pause]" in m]
    assert len(kinds) == 2


def test_a_ban_is_told_even_when_it_ends_before_the_pause_that_was_running(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A ban changes what the owner must do (it is the IP, not the rate), whatever its end."""
    policy, gate = _policy()
    caplog.set_level(logging.DEBUG, logger="App.TradingAdapter")

    _refuse_with(
        policy,
        rate_limited(418, retry_after="5"),
        while_in_flight=lambda: policy.note_used_weight(900),
    )

    told = _told(caplog)
    assert len(told) == 2, told
    assert "[rate-limit-ban]" in told[1]
    assert gate.banned
    soft_end = told[0].split("until ")[1].split(" ")[0]
    assert f"until {soft_end}" in told[1], "the end the gate holds, not the ban's own"


def test_a_ban_is_told_again_in_the_next_pause_once_the_first_has_ended(
    caplog: pytest.LogCaptureFixture,
) -> None:
    gate_now = [0.0]
    gate = RateLimitGate(lambda: gate_now[0])
    policy = ExchangeCallPolicy(gate, weight_limit=1200, wall_seconds=lambda: _WALL)
    caplog.set_level(logging.DEBUG, logger="App.TradingAdapter")
    _refuse_with(policy, rate_limited(418, retry_after="10"))
    gate_now[0] += 11.0
    assert policy.run_read(lambda: "answer") == "answer"  # the pause is over

    _refuse_with(
        policy,
        rate_limited(418, retry_after="5"),
        while_in_flight=lambda: policy.note_used_weight(900),
    )

    bans = [m for m in _told(caplog) if "[rate-limit-ban]" in m]
    assert len(bans) == 2, "the first ban's flag must not outlive its pause"
