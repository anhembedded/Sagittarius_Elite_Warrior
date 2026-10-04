"""`EPIC-029E` — a bot's orders keep the budget's spacing apart (ADR D6 check 4).

The pacer runs on a clock the test moves; its sleep advances that clock, so
what it waited is read back exactly and nothing really sleeps.
"""

from __future__ import annotations

import math
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
