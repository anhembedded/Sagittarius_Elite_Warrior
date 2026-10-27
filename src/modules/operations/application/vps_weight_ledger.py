"""`EPIC-047H` — the weight the host's reads for the VPS tab spent in the last minute, and when there is room for more.

@details Everything the refresh and the backfill read is charged here, by the weight the exchange
reported where it could be seen (`vps_refresh_costs.measured_weight`) and by a conservative
estimate where it could not. The ceiling is a share of the venue's per-minute weight
(`VpsFeedSettings.ceiling_pct`); `seconds_until_room` is how long a read of a given cost must wait
for the minute's window to hold it, which is how the interval *stretches* with the number of bots
and never bursts: a read that does not fit waits for the entries that make it not fit to age out.

Not thread-safe by design: the refresher's single worker is the only caller.
"""

from __future__ import annotations

import math
from collections import deque

#: The window the venue counts weight in.
WINDOW_S = 60.0


class WeightLedger:
    def __init__(self) -> None:
        self._entries: deque[tuple[float, int]] = deque()

    def charge(self, weight: int, at: float) -> None:
        """Record `weight` spent at monotonic second `at`. A negative amount is not a charge."""
        if weight > 0:
            self._entries.append((at, weight))

    def spent(self, now: float) -> int:
        """The weight charged inside the window that ends at `now`."""
        self._forget_before(now)
        return sum(weight for _, weight in self._entries)

    def seconds_until_room(self, need: int, ceiling: int, now: float) -> float:
        """0 when `need` fits under `ceiling` now; else the seconds until enough entries have aged out of
        the window; `math.inf` when `need` alone exceeds the ceiling (it can never fit)."""
        if need > ceiling:
            return math.inf
        self._forget_before(now)
        excess = sum(weight for _, weight in self._entries) + need - ceiling
        if excess <= 0:
            return 0.0
        freed = 0
        for at, weight in self._entries:
            freed += weight
            if freed >= excess:
                return max(at + WINDOW_S - now, 0.0)
        return WINDOW_S

    def _forget_before(self, now: float) -> None:
        while self._entries and self._entries[0][0] <= now - WINDOW_S:
            self._entries.popleft()
