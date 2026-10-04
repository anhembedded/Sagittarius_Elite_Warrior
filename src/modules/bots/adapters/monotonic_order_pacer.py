"""`EPIC-029E` — `IOrderPacer` on the monotonic clock."""

from __future__ import annotations

import time
from datetime import timedelta

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_order_pacer import (
    IOrderPacer,
)


class MonotonicOrderPacer(IOrderPacer):
    """Sleeps the rest of `spacing` since the last turn, then takes it."""

    def __init__(self, spacing: timedelta) -> None:
        self._spacing = spacing.total_seconds()
        self._last: float | None = None

    def wait_turn(self) -> None:
        now = time.monotonic()
        if self._last is not None:
            wait = self._last + self._spacing - now
            if wait > 0:
                time.sleep(wait)
                now = time.monotonic()
        self._last = now
