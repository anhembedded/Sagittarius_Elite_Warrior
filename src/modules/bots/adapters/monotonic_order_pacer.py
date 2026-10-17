"""`EPIC-029E`, `EPIC-029J` J1b — `IOrderPacer` on the monotonic clock.

The clock and the sleep are injected so a test drives them (`testing-rule.md`:
no sleeps); the composition root takes the defaults, the process's own.

One pacer serves every bot of a venue (`VenueOrderPacers`), and each bot's worker is its own
thread, so a turn is reserved under a lock and waited for outside it: two threads never take
the same instant, and a long wait never holds the others' reservations.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from datetime import timedelta

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_order_pacer import (
    IOrderPacer,
)


class MonotonicOrderPacer(IOrderPacer):
    """Gives each caller the next instant at least `spacing` after the previous one's."""

    def __init__(
        self,
        spacing: timedelta,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._spacing = spacing.total_seconds()
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.Lock()
        self._last: float | None = None

    def wait_turn(self) -> None:
        with self._lock:
            now = self._clock()
            turn = now if self._last is None else max(now, self._last + self._spacing)
            self._last = turn
        wait = turn - now
        if wait > 0:
            self._sleep(wait)
