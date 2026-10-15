"""`BUG-216` (review of PR #528) - a minute at 70 % of its weight stays closed to its end, short pause or not.

@details A `-1015` pauses for 10 s by default and a `Retry-After` can be shorter than what is left of
the minute. If an answer reports 70 % or more while such a pause runs, the gate must still close to
the minute's end: skipping the whole branch because a pause is running would let the chains go out
again inside a minute that is already nearly spent. Only the telling is skipped (one WARNING per
pause, `test_exchange_call_policy.py`).
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

_LIMIT = 1200
_OVER = 900  # 75 % of the limit


def test_a_short_pause_already_running_is_extended_to_the_end_of_the_minute() -> None:
    now = [0.0]
    gate = RateLimitGate(lambda: now[0])
    policy = ExchangeCallPolicy(
        gate, weight_limit=_LIMIT, wall_seconds=lambda: 600.0 + 20.0
    )
    gate.block(10.0)  # a `-1015`, say: 10 s, with 41 s of the minute left

    policy.note_used_weight(_OVER)

    assert gate.remaining() == pytest.approx(41.0), "40 s left of the minute, +1"


def test_the_extension_is_not_told_a_second_time(
    caplog: pytest.LogCaptureFixture,
) -> None:
    now = [0.0]
    gate = RateLimitGate(lambda: now[0])
    policy = ExchangeCallPolicy(
        gate, weight_limit=_LIMIT, wall_seconds=lambda: 600.0 + 20.0
    )
    gate.block(10.0)
    caplog.set_level(logging.DEBUG, logger="App.TradingAdapter")

    policy.note_used_weight(_OVER)

    assert [r for r in caplog.records if r.levelno >= logging.INFO] == []
