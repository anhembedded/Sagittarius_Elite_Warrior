"""`EPIC-035A` — `IMonotonicClock` on `time.monotonic`."""

from __future__ import annotations

import time

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_monotonic_clock import (
    IMonotonicClock,
)


class SystemMonotonicClock(IMonotonicClock):
    """The process's own monotonic clock."""

    def seconds(self) -> float:
        return time.monotonic()
