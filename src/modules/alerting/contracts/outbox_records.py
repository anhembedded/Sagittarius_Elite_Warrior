"""The shapes that cross the `IOutbox` port."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert import Alert
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.delivery_state import (
    DeliveryState,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.loudness import Loudness


@dataclass(frozen=True, slots=True)
class DeliveryTarget:
    """One channel an alert is queued for. `state` is `PENDING`, or `DROPPED` for
    a delivery the queue had no room for (recorded, never silently lost)."""

    channel_id: str
    loudness: Loudness
    state: DeliveryState = DeliveryState.PENDING


@dataclass(frozen=True, slots=True)
class AlertRecord:
    """One alert as stored: `count` is how many times it happened in its window."""

    alert_id: int
    alert: Alert
    count: int
    last_at: datetime


@dataclass(frozen=True, slots=True)
class DeliveryRecord:
    delivery_id: int
    alert_id: int
    channel_id: str
    loudness: Loudness
    state: DeliveryState
    attempts: int
    next_attempt_at: datetime
    reason: str


@dataclass(frozen=True, slots=True)
class DueDelivery:
    """A delivery ready to try, with the alert it carries."""

    delivery: DeliveryRecord
    alert: Alert


@dataclass(frozen=True, slots=True)
class DeliveryUpdate:
    """The outcome of one try, as the outbox stores it."""

    state: DeliveryState
    attempts: int
    next_attempt_at: datetime
    reason: str


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    record: AlertRecord
    deliveries: tuple[DeliveryRecord, ...]


@dataclass(frozen=True, slots=True)
class OutboxBacklog:
    """What is waiting: how many deliveries, and how long the oldest has waited."""

    depth: int
    oldest_age: timedelta | None
