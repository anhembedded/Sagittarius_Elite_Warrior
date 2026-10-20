"""One open warning per key and a cool-down between two raises (`EPIC-036B1`).

The hub dedups an identical alert inside a window but forgets the window when a source clears the
condition, so a condition that flips between raised and cleared would send a pair each time. This
latch is the source's side of the bargain: a key is raised only when it is not open and its last
raise is older than the cool-down, and it is cleared only when a raise reached the hub.

`defer_clear` is for a condition whose raise is not repeated by new events while it stands (a
liquidation warning is published once per change of level): a clear inside the cool-down is
refused, so the owner is never left with a "Recovered" that a held-back re-raise has made false,
and a raise on a key still open after the cool-down is told again as a reminder. Without it
(a stream outage, which new events keep re-announcing) a clear is always honoured and an open key
is never raised twice.

Not thread-safe by itself; the owning source holds its lock around every call.
"""

from __future__ import annotations

from datetime import datetime, timedelta


class WarningLatch:
    def __init__(self, cooldown: timedelta, defer_clear: bool = False) -> None:
        self._cooldown = cooldown
        self._defer_clear = defer_clear
        self._raised_at: dict[str, datetime] = {}
        self._open: set[str] = set()

    def is_open(self, key: str) -> bool:
        return key in self._open

    def raise_(self, key: str, now: datetime) -> bool:
        """`True` when the caller should publish the warning for `key` now."""
        last = self._raised_at.get(key)
        if key in self._open and not self._defer_clear:
            return False
        if last is not None and now - last < self._cooldown:
            return False
        self._open.add(key)
        self._raised_at[key] = now
        return True

    def clear(self, key: str, now: datetime) -> bool:
        """`True` when `key` was open and its recovery is due; `False` when it was not open, or
        (with `defer_clear`) was raised less than a cool-down ago and so stays open."""
        if key not in self._open:
            return False
        if self._defer_clear and now - self._raised_at[key] < self._cooldown:
            return False
        self._open.discard(key)
        return True

    def forget(self, key: str) -> None:
        """The subject is gone or no longer judged (a halted or removed bot): drop its memory,
        its cool-down included."""
        self._open.discard(key)
        self._raised_at.pop(key, None)
