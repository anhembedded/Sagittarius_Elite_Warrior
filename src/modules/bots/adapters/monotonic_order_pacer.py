"""`EPIC-029E` — `IOrderPacer` on the monotonic clock.

The clock and the sleep are injected so a test drives them (`testing-rule.md`:
no sleeps); the composition root takes the defaults, the process's own.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import timedelta

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_order_pacer import (
    IOrderPacer,
)


class MonotonicOrderPacer(IOrderPacer):
    """Sleeps the rest of `spacing` since the last turn, then takes it."""

    def __init__(
        self,
        spacing: timedelta,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._spacing = spacing.total_seconds()
        self._clock = clock
        self._sleep = sleep
        self._last: float | None = None

    def wait_turn(self) -> None:
        now = self._clock()
        if self._last is not None:
            wait = self._last + self._spacing - now
            if wait > 0:
                self._sleep(wait)
                now = self._clock()
        self._last = now
