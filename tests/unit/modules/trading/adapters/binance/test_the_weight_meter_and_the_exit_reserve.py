"""`EPIC-047H` - the host's reads for the VPS tab cannot spend the exit reserve; the meter shows the policy's own gate.

The refresh runs at `ROUTINE` and is read through `PolicyWeightMeter`. Here the real `ExchangeCallPolicy`
(its real gate) is the venue: past 70 % of the minute's weight a routine request is not sent while a request
that guards an exit still is, and the meter reports exactly that gate and the last used-weight header.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.exchange_call_policy import (
    ExchangeCallPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.policy_weight_meter import (
    PolicyWeightMeter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.rate_limit_gate import (
    RateLimitGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.rate_limited_api_exception import (
    RateLimitedApiException,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.request_priority import (
    RequestPriority,
    prioritised,
)

LIMIT = 2400
WALL = 1_800_000_020.0


def _policy() -> ExchangeCallPolicy:
    return ExchangeCallPolicy(
        RateLimitGate(), weight_limit=LIMIT, wall_seconds=lambda: WALL
    )


def test_before_any_answer_the_meter_knows_no_weight_and_the_gate_is_open() -> None:
    reading = PolicyWeightMeter(_policy()).read()

    assert (reading.used, reading.seen_at, reading.limit) == (None, None, LIMIT)
    assert reading.routine_open


def test_the_meter_reports_the_last_header_and_when_it_was_seen() -> None:
    policy = _policy()

    policy.note_used_weight_header("96")

    reading = PolicyWeightMeter(policy).read()
    assert (reading.used, reading.seen_at) == (96, WALL)
    assert reading.routine_open


def test_past_the_soft_line_the_meter_says_routine_is_closed_and_a_routine_read_is_not_sent() -> (
    None
):
    policy = _policy()
    policy.note_used_weight(int(LIMIT * 0.7) + 20)
    sent: list[str] = []

    assert not PolicyWeightMeter(policy).read().routine_open
    with pytest.raises(RateLimitedApiException), prioritised(RequestPriority.ROUTINE):
        policy.run_read(lambda: sent.append("refresh"))

    assert sent == []


def test_a_read_that_guards_an_exit_still_passes_in_the_reserve() -> None:
    policy = _policy()
    policy.note_used_weight(int(LIMIT * 0.7) + 20)
    sent: list[str] = []

    with prioritised(RequestPriority.EXIT_GUARD):
        policy.run_read(lambda: sent.append("exit guard"))

    assert sent == ["exit guard"]
    assert not PolicyWeightMeter(policy).read().routine_open


def test_at_the_hard_line_nothing_passes_and_the_reserve_is_over() -> None:
    policy = _policy()
    policy.note_used_weight(int(LIMIT * 0.9) + 1)

    with (
        pytest.raises(RateLimitedApiException),
        prioritised(RequestPriority.EXIT_GUARD),
    ):
        policy.run_read(lambda: None)
