"""`IOutbox` — alerts and their deliveries, kept until they are done (N2).

The **transactional outbox**: an alert is stored *before* any send is tried and
the worker reads from the store, so an alert raised while the network is down, or
just before the app stops, is sent on return. A delivery stays open until
`mark` records its outcome, which makes delivery **at-least-once**: a process
that dies between the channel accepting a message and `mark` sends it again.

Safe from any thread. Operations are short and none holds a lock across a
channel call.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import datetime

from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.outbox_records import (
    DeliveryTarget,
    DeliveryUpdate,
    DueDelivery,
    HistoryEntry,
    OutboxBacklog,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert import Alert
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.severity import Severity


class IOutbox(ABC):
    @abstractmethod
    def enqueue(
        self, alert: Alert, targets: Sequence[DeliveryTarget], now: datetime
    ) -> int:
        """Store `alert` with one delivery per target, due at `now`; its id.
        No target stores the alert alone (muted, or no route)."""

    @abstractmethod
    def add_delivery(self, alert_id: int, target: DeliveryTarget, now: datetime) -> int:
        """Queue a stored alert for one more channel (fail-over); the delivery id."""

    @abstractmethod
    def bump(self, alert_id: int, at: datetime) -> None:
        """The alert happened again: count it and remember when. Sends nothing."""

    @abstractmethod
    def channels_of(self, alert_id: int) -> frozenset[str]:
        """Every channel holding a delivery of the alert, in any state."""

    @abstractmethod
    def due(
        self, channel_id: str, now: datetime, limit: int
    ) -> tuple[DueDelivery, ...]:
        """Open deliveries of `channel_id` whose time has come: CRITICAL first,
        then the oldest."""

    @abstractmethod
    def mark(self, delivery_id: int, update: DeliveryUpdate) -> None:
        """Record the outcome of one try."""

    @abstractmethod
    def expire_before(self, cutoff: datetime) -> int:
        """Mark every open delivery of an alert raised before `cutoff` expired;
        how many."""

    @abstractmethod
    def pending_count(self, channel_id: str) -> int:
        """Open deliveries of `channel_id`."""

    @abstractmethod
    def shed_lowest(self, channel_id: str, below: Severity) -> bool:
        """Drop the oldest open delivery of the lowest severity strictly below
        `below` on `channel_id` (kept as `DROPPED`, not deleted). `False` when
        nothing is below."""

    @abstractmethod
    def purge_finished_before(self, cutoff: datetime) -> int:
        """Delete alerts last seen before `cutoff` that have no open delivery;
        how many."""

    @abstractmethod
    def history(self, limit: int) -> tuple[HistoryEntry, ...]:
        """The newest `limit` alerts with their deliveries."""

    @abstractmethod
    def backlog(self, now: datetime) -> OutboxBacklog:
        """How many deliveries are open and the age of the oldest."""

    @abstractmethod
    def close(self) -> None:
        """Release the store. Further calls are a programming error."""
