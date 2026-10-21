"""`EPIC-035D` — the pause a venue's exchange asked for, shared by every call of the venue.

One gate per venue session factory: the account reader, the trading client, the
history readers and the bots' own reads all go through the same sessions, so a
429 seen by any of them closes the gate for all of them. While it is closed no
request is sent, which is what keeps a 429 from becoming a 418 (the exchange
bans an IP that keeps sending after being told to stop).

The clock is injected (`time.monotonic` in production): a wall-clock step cannot
shorten or lengthen a pause. It is the same clock the order pacer takes, in the
same shape; this module sits below `bots` and cannot import its clock port.

A second, narrower deadline closes the gate to routine traffic only (`BOT-226`): the weight
reserve between the 70 % line and the hard line (`ExchangeCallPolicy`). It never outlasts or
replaces the first; a request that guards an exit asks `remaining`, any other `routine_remaining`.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable


class RateLimitGate:
    """Closed until a deadline; a later block only ever extends it."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._open_at = 0.0
        self._routine_open_at = 0.0
        self._banned_until = 0.0

    def block(self, seconds: float, *, banned: bool = False) -> None:
        """Close the gate for `seconds` from now, or keep it closed longer."""
        until = self._clock() + seconds
        with self._lock:
            self._open_at = max(self._open_at, until)
            if banned:
                self._banned_until = max(self._banned_until, until)

    def block_routine(self, seconds: float) -> None:
        """Close the gate to routine requests for `seconds` from now, or keep it closed longer;
        the requests that guard an exit are not held by this."""
        until = self._clock() + seconds
        with self._lock:
            self._routine_open_at = max(self._routine_open_at, until)

    def remaining(self) -> float:
        """Seconds until the gate opens to every request; zero when it is open."""
        with self._lock:
            return max(self._open_at - self._clock(), 0.0)

    def routine_remaining(self) -> float:
        """Seconds until the gate opens to a routine request: the later of the pause that holds
        everything and the reserve's."""
        with self._lock:
            reserve = max(self._routine_open_at - self._clock(), 0.0)
        return max(self.remaining(), reserve)

    @property
    def banned(self) -> bool:
        """Whether the pause now running is an IP ban."""
        with self._lock:
            return self._banned_until > self._clock()
