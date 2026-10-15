"""`BUG-216` - what a Futures venue last learned of its account's position mode.

Reading the mode weighs 30, a connection check runs for every order and every poll, and the mode
is the user's to change on the exchange. So a One-way answer is trusted for `TTL_SECONDS`; a Hedge
answer and a failed read are never kept. The order path also forgets it: an order sent as One-way
(`positionSide=BOTH`) that the exchange refuses with `-4061` says the account is no longer One-way,
and the next check must read the mode rather than wait out the minute. Shared by the venue's
account reader and its trading clients; orders run on other threads, so it holds a lock.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

TTL_SECONDS = 60.0


class PositionModeMemory:
    """When a One-way answer was last read, or nothing."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._one_way_read_at: float | None = None

    def one_way_is_current(self) -> bool:
        """Whether a One-way answer read less than `TTL_SECONDS` ago is still trusted."""
        with self._lock:
            read_at = self._one_way_read_at
        return read_at is not None and 0 <= self._clock() - read_at < TTL_SECONDS

    def remember_one_way(self) -> None:
        with self._lock:
            self._one_way_read_at = self._clock()

    def forget(self) -> None:
        with self._lock:
            self._one_way_read_at = None
