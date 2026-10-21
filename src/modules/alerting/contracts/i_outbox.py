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
from collections.abc import Mapping, Sequence
from datetime import datetime

from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.outbox_records import (
    DeliveryRecord,
    DeliveryTarget,
    DeliveryUpdate,
    DueDelivery,
    HistoryEntry,
    OutboxBacklog,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert import Alert
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
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
    def retry_horizon(self, channel_id: str) -> datetime | None:
        """The latest time any open `RETRYING` delivery of `channel_id` waits for;
        `None` when none does. How a restarted worker knows the channel asked it
        to wait."""

    @abstractmethod
    def pending_count(self, channel_id: str) -> int:
        """Open deliveries of `channel_id`."""

    @abstractmethod
    def shed_lowest(self, channel_id: str, below: Severity) -> bool:
        """Drop the oldest open delivery of the lowest severity strictly below
        `below` on `channel_id` (kept as `DROPPED`, not deleted). `False` when
        nothing is below."""

    @abstractmethod
    def shed_surplus(self, channel_id: str, kind: AlertKind, keep: int) -> int:
        """Drop the oldest open deliveries of alerts of `kind` on `channel_id` until `keep` are
        left (kept as `DROPPED`, not deleted); how many were dropped (`BOT-189`)."""

    @abstractmethod
    def purge_finished_before(self, cutoff: datetime) -> int:
        """Delete alerts last seen before `cutoff` that have no open delivery;
        how many."""

    @abstractmethod
    def history(self, limit: int) -> tuple[HistoryEntry, ...]:
        """The newest `limit` alerts with their deliveries."""

    @abstractmethod
    def latest_real_delivery(self, channel_id: str) -> DeliveryRecord | None:
        """The newest delivery on `channel_id` that says whether the channel works: sent, failed,
        expired or retrying. A pending or dropped delivery says nothing. `None` when there is none. Not bounded
        by a history window: a channel's health must not depend on how many alerts queued behind
        its head (`EPIC-036D3`)."""

    @abstractmethod
    def latest_alert_at(self, kind: AlertKind) -> datetime | None:
        """When the newest stored alert of `kind` was raised; `None` when there is none.
        What a scheduled sender reads back after a restart (`EPIC-036E`), whatever else has been
        stored since."""

    @abstractmethod
    def has_alert_keyed(self, dedup_key: str) -> bool:
        """Whether an alert with exactly this dedup key is stored."""

    @abstractmethod
    def alert_counts_since(self, since: datetime) -> Mapping[AlertKind, int]:
        """How many alerts of each kind happened at or after `since`, a repeat counted each
        time it happened (`AlertRecord.count`). Exact, not bounded by a history window."""

    @abstractmethod
    def backlog(self, now: datetime) -> OutboxBacklog:
        """How many deliveries are open and the age of the oldest."""

    @abstractmethod
    def close(self) -> None:
        """Release the store. Further calls are a programming error."""
