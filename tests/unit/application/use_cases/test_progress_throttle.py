"""Tests for `ProgressThrottle` (BUG-033) — the wall-clock-time gate that
replaced both backtest handlers' index-based `index % N == 0` progress
throttle, which fired proportionally to tick/bar count and froze the UI
thread for 5.2s on a real 2.59M-tick run."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.application.use_cases.backtest.progress_throttle import (
    ProgressThrottle,
)


class _FakeClock:
    """Deterministic stand-in for `time.perf_counter` — advances only when
    told to, so tests never depend on real elapsed wall-clock time."""

    def __init__(self, start: float = 0.0) -> None:
        self._now = start

    def advance(self, seconds: float) -> None:
        self._now += seconds

    def __call__(self) -> float:
        return self._now


def test_always_emits_on_the_first_index():
    throttle = ProgressThrottle(clock=_FakeClock())

    assert throttle.should_emit(1, 1000) is True


def test_always_emits_on_the_last_index():
    clock = _FakeClock()
    throttle = ProgressThrottle(clock=clock)
    throttle.should_emit(1, 1000)

    assert throttle.should_emit(1000, 1000) is True


def test_a_single_element_run_emits_once():
    """index == 1 and index == total at the same time — must not require
    two separate conditions to both be satisfied."""
    throttle = ProgressThrottle(clock=_FakeClock())

    assert throttle.should_emit(1, 1) is True


def test_suppresses_intermediate_calls_within_the_interval():
    clock = _FakeClock()
    throttle = ProgressThrottle(min_interval_seconds=0.15, clock=clock)
    throttle.should_emit(1, 1000)  # primes _last_emit_time

    clock.advance(0.05)
    assert throttle.should_emit(2, 1000) is False
    clock.advance(0.05)
    assert throttle.should_emit(3, 1000) is False


def test_emits_again_once_the_interval_has_elapsed():
    clock = _FakeClock()
    throttle = ProgressThrottle(min_interval_seconds=0.15, clock=clock)
    throttle.should_emit(1, 1000)

    clock.advance(0.20)

    assert throttle.should_emit(2, 1000) is True


def test_call_rate_is_bounded_regardless_of_iteration_count():
    """The behaviour BUG-033 actually needs: for a run whose real duration
    is much larger than the throttle interval, the number of emitted
    updates is bounded by (duration / interval), never by the iteration
    count itself. Simulates 1,000,000 iterations over 2 real seconds with a
    150ms interval — old index-based throttling (`% 256`) would have fired
    ~3,900 times here; time-based throttling fires roughly 2s / 0.15s ≈ 14
    times."""
    clock = _FakeClock()
    throttle = ProgressThrottle(min_interval_seconds=0.15, clock=clock)
    total = 1_000_000
    emit_count = 0

    for index in range(1, total + 1):
        clock.advance(2.0 / total)
        if throttle.should_emit(index, total):
            emit_count += 1

    assert emit_count < 20


def test_resuming_after_a_long_gap_does_not_burst():
    """A single stale `_last_emit_time` must not cause every subsequent
    call to fire until it catches up — should_emit() always re-arms to
    "now" on every True, so a big gap only ever produces one emit, not a
    burst once elapsed time is finally checked again."""
    clock = _FakeClock()
    throttle = ProgressThrottle(min_interval_seconds=0.15, clock=clock)
    throttle.should_emit(1, 1000)

    clock.advance(5.0)  # a long real-world pause

    assert throttle.should_emit(2, 1000) is True
    assert throttle.should_emit(3, 1000) is False
