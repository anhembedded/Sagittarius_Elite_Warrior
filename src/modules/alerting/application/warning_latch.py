"""One open warning per key and a cool-down between two raises (`EPIC-036B1`).

The hub dedups an identical alert inside a window but forgets the window when a source clears the
condition, so a condition that flips between raised and cleared would send a pair each time. This
latch is the source's side of the bargain: a key is raised only when it is not open and its last
raise is older than the cool-down, and it is cleared only when a raise reached the hub.

Not thread-safe by itself; the owning source holds its lock around every call.
"""

from __future__ import annotations

from datetime import datetime, timedelta


class WarningLatch:
    def __init__(self, cooldown: timedelta) -> None:
        self._cooldown = cooldown
        self._raised_at: dict[str, datetime] = {}
        self._open: set[str] = set()

    def raise_(self, key: str, now: datetime) -> bool:
        """`True` when the caller should publish the warning for `key` now."""
        if key in self._open:
            return False
        last = self._raised_at.get(key)
        if last is not None and now - last < self._cooldown:
            return False
        self._open.add(key)
        self._raised_at[key] = now
        return True

    def clear(self, key: str) -> bool:
        """`True` when `key` was open, i.e. a raise reached the hub and its recovery is due."""
        if key not in self._open:
            return False
        self._open.discard(key)
        return True

    def forget(self, key: str) -> None:
        """The subject is gone (a removed bot): drop its memory."""
        self._open.discard(key)
        self._raised_at.pop(key, None)
