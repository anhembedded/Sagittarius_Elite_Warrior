"""What the Alerts screen reads: the newest alerts and where each one went (`EPIC-036D2`)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.delivery_state import (
    DeliveryState,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.severity import Severity


@dataclass(frozen=True, slots=True)
class ChannelOutcome:
    """Where one alert stands on one channel."""

    channel_id: str
    state: DeliveryState
    attempts: int


@dataclass(frozen=True, slots=True)
class AlertHistoryRow:
    """One stored alert. `count` is how many times it happened in its window; `at` is the
    time it was last seen."""

    alert_id: int
    at: datetime
    kind: AlertKind
    severity: Severity
    subject: str
    title: str
    count: int
    outcomes: tuple[ChannelOutcome, ...]


@dataclass(frozen=True, slots=True)
class ChannelHealth:
    """One channel this run has. `failing` when its newest delivery did not get through
    (retrying, failed or expired); `waiting` is how many deliveries are still open."""

    channel_id: str
    failing: bool
    waiting: int


@dataclass(frozen=True, slots=True)
class AlertHistoryReport:
    """The newest alerts first, and the state of every channel."""

    rows: tuple[AlertHistoryRow, ...]
    channels: tuple[ChannelHealth, ...]
