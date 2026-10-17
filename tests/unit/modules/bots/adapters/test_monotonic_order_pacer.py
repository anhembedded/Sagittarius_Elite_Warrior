"""`EPIC-029E` — a bot's orders keep the budget's spacing apart (ADR D6 check 4).

The pacer runs on a clock the test moves; its sleep advances that clock, so
what it waited is read back exactly and nothing really sleeps.
"""

from __future__ import annotations

import math
import threading
from datetime import timedelta
from itertools import pairwise

from Sagittarius_Elite_Warrior.src.modules.bots.adapters.monotonic_order_pacer import (
    MonotonicOrderPacer,
)

_SPACING = timedelta(milliseconds=250)


class _Clock:
    def __init__(self) -> None:
        self.now = 100.0
        self.slept: list[float] = []

    def read(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def _pacer(clock: _Clock) -> MonotonicOrderPacer:
    return MonotonicOrderPacer(_SPACING, clock.read, clock.sleep)


def test_the_first_turn_is_taken_at_once() -> None:
    clock = _Clock()

    _pacer(clock).wait_turn()

    assert clock.slept == []


def test_a_turn_sooner_than_the_spacing_waits_the_rest_of_it() -> None:
    clock = _Clock()
    pacer = _pacer(clock)
    pacer.wait_turn()
    clock.now += 0.1

    pacer.wait_turn()

    assert len(clock.slept) == 1
    assert math.isclose(clock.slept[0], 0.15)


def test_a_turn_at_or_after_the_spacing_does_not_wait() -> None:
    clock = _Clock()
    pacer = _pacer(clock)
    pacer.wait_turn()
    clock.now += 0.25
    pacer.wait_turn()
    clock.now += 1.0

    pacer.wait_turn()

    assert clock.slept == []


def test_ten_slices_in_a_row_are_each_a_spacing_apart() -> None:
    """The task's exit: ten tagged slices, 250 ms apart."""
    clock = _Clock()
    pacer = _pacer(clock)
    taken: list[float] = []

    for _ in range(10):
        pacer.wait_turn()
        taken.append(clock.now)

    gaps = [later - earlier for earlier, later in pairwise(taken)]
    assert len(gaps) == 9
    assert all(math.isclose(gap, 0.25) for gap in gaps)


def test_bots_sharing_a_pacer_are_a_spacing_apart_from_each_other() -> None:
    """`EPIC-029J` J1b: one pacer per venue, so the venue's orders keep the spacing whoever sends."""
    clock = _Clock()
    pacer = _pacer(clock)
    taken: list[float] = []

    for _bot in ("a", "b", "c"):
        pacer.wait_turn()
        taken.append(clock.now)

    gaps = [later - earlier for earlier, later in pairwise(taken)]
    assert all(math.isclose(gap, 0.25) for gap in gaps)


class _SteadyClock:
    """A clock that does not move and a sleep that only records: every caller reads the same
    instant, which is the worst case for two threads reserving the same turn."""

    def __init__(self) -> None:
        self.slept: list[float] = []
        self._lock = threading.Lock()

    def read(self) -> float:
        return 100.0

    def sleep(self, seconds: float) -> None:
        with self._lock:
            self.slept.append(seconds)


def test_threads_asking_at_the_same_instant_each_reserve_a_turn_of_their_own() -> None:
    """Each bot's worker is its own thread; two never take the same slot."""
    clock = _SteadyClock()
    pacer = MonotonicOrderPacer(_SPACING, clock.read, clock.sleep)
    workers = 8
    start = threading.Barrier(workers)

    def turn() -> None:
        start.wait()
        pacer.wait_turn()

    threads = [threading.Thread(target=turn) for _ in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    waits = sorted(clock.slept)
    expected = [0.25 * turn_number for turn_number in range(1, workers)]
    assert len(waits) == workers - 1, "the first caller took its turn at once"
    assert all(
        math.isclose(got, want) for got, want in zip(waits, expected, strict=True)
    )
