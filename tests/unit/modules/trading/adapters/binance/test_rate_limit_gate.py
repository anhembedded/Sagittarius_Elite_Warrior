"""`EPIC-035D` — the venue-wide pause: one gate, shared by every call of a venue."""

from __future__ import annotations

import threading

from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.rate_limit_gate import (
    RateLimitGate,
)


class _Clock:
    def __init__(self) -> None:
        self.at = 100.0

    def __call__(self) -> float:
        return self.at


def test_an_open_gate_has_nothing_remaining() -> None:
    gate = RateLimitGate(_Clock())
    assert (gate.remaining(), gate.banned) == (0.0, False)


def test_a_blocked_gate_counts_down_and_reopens_exactly_at_the_end() -> None:
    clock = _Clock()
    gate = RateLimitGate(clock)

    gate.block(30.0)
    clock.at += 10
    assert gate.remaining() == 20.0
    clock.at += 20
    assert gate.remaining() == 0.0
    assert gate.banned is False


def test_a_second_block_only_ever_extends_the_pause() -> None:
    clock = _Clock()
    gate = RateLimitGate(clock)

    gate.block(60.0)
    gate.block(5.0)
    assert gate.remaining() == 60.0
    gate.block(90.0)
    assert gate.remaining() == 90.0


def test_a_ban_is_remembered_until_it_ends() -> None:
    clock = _Clock()
    gate = RateLimitGate(clock)

    gate.block(120.0, banned=True)
    assert gate.banned is True
    clock.at += 121
    assert gate.banned is False


def test_a_later_plain_block_does_not_hide_a_running_ban() -> None:
    gate = RateLimitGate(_Clock())
    gate.block(300.0, banned=True)
    gate.block(10.0)
    assert gate.banned is True


def test_blocks_from_many_threads_keep_the_longest() -> None:
    gate = RateLimitGate(_Clock())
    threads = [
        threading.Thread(target=gate.block, args=(float(seconds),))
        for seconds in range(1, 40)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert gate.remaining() == 39.0
