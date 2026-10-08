"""`EPIC-035I` — how long the process was not running between two looks.

A heartbeat that finds more time gone than it was meant to wait has been
suspended: the machine slept or hibernated, or the process was frozen. Two
clocks are read because neither alone sees every case:

  · the **monotonic clock** (`IMonotonicClock`) cannot be set, but on Linux it
    stops while the machine is suspended, and on Windows it keeps running;
  · the **wall clock** (`IBotClock`) counts the sleep everywhere, but a person
    or a time service can step it. A step back is ignored (a negative elapsed
    time); a step forward reads as a sleep, and the catch-up it causes changes
    nothing when nothing was missed.

The larger of the two elapsed times wins.
"""

from __future__ import annotations

from datetime import timedelta

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_clock import IBotClock
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_monotonic_clock import (
    IMonotonicClock,
)


class ClockGapDetector:
    """Answers, at each look, how much longer than expected it has been."""

    def __init__(
        self, monotonic: IMonotonicClock, wall: IBotClock, gap_over: timedelta
    ) -> None:
        self._monotonic = monotonic
        self._wall = wall
        self._gap_over = gap_over
        self._seen_monotonic = monotonic.seconds()
        self._seen_wall = wall.now()

    def look(self, expected: timedelta) -> timedelta | None:
        """The time the process was away beyond `expected`, or `None` when it
        was away for no more than `expected + gap_over`. Moves the look point."""
        monotonic_now = self._monotonic.seconds()
        wall_now = self._wall.now()
        elapsed = max(
            timedelta(seconds=monotonic_now - self._seen_monotonic),
            wall_now - self._seen_wall,
        )
        self._seen_monotonic = monotonic_now
        self._seen_wall = wall_now
        if elapsed - expected > self._gap_over:
            return elapsed
        return None
