"""`EPIC-035B` — the thread that drives the user-stream watch's `check()`.

Waits on a named signal (the tick), never on a sleep: the interval is a few
milliseconds and each assertion blocks on the event the tick sets."""

from __future__ import annotations

import threading
from datetime import timedelta

from Sagittarius_Elite_Warrior.src.modules.bots.adapters.thread_periodic_timer import (
    ThreadPeriodicTimer,
)

_WAIT_SECONDS = 5.0


def test_a_started_timer_ticks_until_stopped() -> None:
    ticks = threading.Semaphore(0)
    timer = ThreadPeriodicTimer("test-timer", timedelta(milliseconds=5), ticks.release)

    timer.start()
    try:
        assert ticks.acquire(timeout=_WAIT_SECONDS)
        assert ticks.acquire(timeout=_WAIT_SECONDS), "it repeats"
    finally:
        timer.stop()

    assert not _alive("test-timer")


def test_a_tick_that_raises_does_not_end_the_timer() -> None:
    ticks = threading.Semaphore(0)
    calls = 0

    def tick() -> None:
        nonlocal calls
        calls += 1
        ticks.release()
        if calls == 1:
            raise RuntimeError("one bad pass")

    timer = ThreadPeriodicTimer("test-timer-raises", timedelta(milliseconds=5), tick)

    timer.start()
    try:
        assert ticks.acquire(timeout=_WAIT_SECONDS)
        assert ticks.acquire(timeout=_WAIT_SECONDS), "it carried on"
    finally:
        timer.stop()


def test_a_timer_never_started_stops_cleanly() -> None:
    ThreadPeriodicTimer("never", timedelta(seconds=1), lambda: None).stop()


def _alive(name: str) -> bool:
    return any(t.name == name and t.is_alive() for t in threading.enumerate())
