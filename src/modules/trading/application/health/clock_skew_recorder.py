"""The last clock skew the host measured against each venue's exchange (`EPIC-038D`).

`IHealthContributor.snapshot()` answers from memory and may not ask the exchange,
so the measurement is made elsewhere (`ClockSkewProbe`, on the `run` host's health
interval) and left here. One entry per venue; a measurement that found nothing
(the exchange did not answer) replaces the last good one with "unknown": a
skew that was true ten minutes ago is not the skew now.
"""

from __future__ import annotations

import threading


class ClockSkewRecorder:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._latest: dict[str, int | None] = {}

    def record(self, venue_name: str, skew_ms: int | None) -> None:
        """Local clock minus the exchange's, in milliseconds; `None` when unread."""
        with self._lock:
            self._latest[venue_name] = skew_ms

    def worst_ms(self) -> int | None:
        """The skew furthest from zero (sign kept), or `None` when no venue has one."""
        with self._lock:
            known = [skew for skew in self._latest.values() if skew is not None]
        return max(known, key=abs) if known else None
