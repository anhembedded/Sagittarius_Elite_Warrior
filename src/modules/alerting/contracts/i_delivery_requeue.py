"""`IDeliveryRequeue` — the owner's "Retry failed" on the outbox (`EPIC-036D5`).

A port of its own and not a method of `IOutbox`: the outbox port is the hub's and the lanes'
(store, claim, mark, expire) and is already wide, and this is the one write the Alerts screen
makes. Holds nothing open between calls. Safe from any thread.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime


class IDeliveryRequeue(ABC):
    @abstractmethod
    def requeue_failed(self, cutoff: datetime, now: datetime) -> int:
        """Put every `FAILED` delivery of an alert raised at or after `cutoff` back to `PENDING`,
        due at `now`, with its attempts counted afresh; how many. An older alert is past the
        expiry and is never sent late (N2), so it stays as it is."""
