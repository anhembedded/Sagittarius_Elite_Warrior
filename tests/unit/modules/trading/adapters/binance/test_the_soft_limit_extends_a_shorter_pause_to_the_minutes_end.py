"""`BUG-217` (found by the review of PR #528) - a minute at 70 % of its weight stays closed to its end, short pause or not.

@details A `-1015` pauses for 10 s by default and a `Retry-After` can be shorter than what is left of
the minute. If an answer reports 70 % or more while such a pause runs, the gate must still close to
the minute's end for the chains: skipping the whole branch because a pause is running would let them
go out again inside a minute that is already nearly spent. Only the telling is skipped (one WARNING
per pause, `test_exchange_call_policy.py`).

Since `BOT-224` the end of the minute binds routine requests from 70 % (`routine_remaining`) and every
request from 90 % (`remaining`); between the two, the reads that guard exits follow the exchange's own
pause. Both halves are tested here: the original path at 75 %, and the hard line at 92 %.
"""

from __future__ import annotations

import logging

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

_LIMIT = 1200
_OVER = 1100  # 92 % of the limit: past the reserve, where the gate closes to everything


def test_a_short_pause_already_running_is_extended_to_the_end_of_the_minute() -> None:
    now = [0.0]
    gate = RateLimitGate(lambda: now[0])
    policy = ExchangeCallPolicy(
        gate, weight_limit=_LIMIT, wall_seconds=lambda: 600.0 + 20.0
    )
    gate.block(10.0)  # a `-1015`, say: 10 s, with 41 s of the minute left

    policy.note_used_weight(_OVER)

    assert gate.remaining() == pytest.approx(41.0), "40 s left of the minute, +1"


def test_in_the_reserve_a_short_pause_is_extended_for_routine_requests_only() -> None:
    """The original `BUG-217` path, at 75 %: the chains wait to the minute's end; the guards wait
    out the exchange's own 10 s and no longer."""
    now = [0.0]
    gate = RateLimitGate(lambda: now[0])
    policy = ExchangeCallPolicy(
        gate, weight_limit=_LIMIT, wall_seconds=lambda: 600.0 + 20.0
    )
    gate.block(10.0)

    policy.note_used_weight(900)

    assert gate.routine_remaining() == pytest.approx(41.0), (
        "40 s left of the minute, +1"
    )
    assert gate.remaining() == pytest.approx(10.0), "the guards follow the pause alone"


def test_in_the_reserve_a_pause_that_ends_first_is_still_extended_for_routine_requests() -> (
    None
):
    now = [0.0]
    gate = RateLimitGate(lambda: now[0])
    policy = ExchangeCallPolicy(
        gate, weight_limit=_LIMIT, wall_seconds=lambda: 600.0 + 20.0
    )
    gate.block(10.0)
    policy.note_used_weight(900)

    now[0] += 11.0  # the exchange's pause is over

    assert gate.remaining() == 0.0
    assert gate.routine_remaining() == pytest.approx(30.0)


def test_the_extension_is_told_once_because_it_moves_the_announced_end(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The 10 s pause is announced (its own end); the soft limit then moves the end to the
    minute's, which is told, and a second answer at 70 % moves nothing and is not."""
    now = [0.0]
    gate = RateLimitGate(lambda: now[0])
    policy = ExchangeCallPolicy(
        gate, weight_limit=_LIMIT, wall_seconds=lambda: 600.0 + 20.0
    )
    caplog.set_level(logging.DEBUG, logger="App.TradingAdapter")

    def call() -> str:
        raise rate_limited(429, code=-1015, retry_after="10")

    with pytest.raises(RateLimitedApiException):
        policy.run_read(call)
    policy.note_used_weight(_OVER)
    policy.note_used_weight(_OVER + 10)

    told = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
    assert len(told) == 2, told
    assert "[rate-limit-pause]" in told[0]
    assert "[rate-limit-soft]" in told[1]
