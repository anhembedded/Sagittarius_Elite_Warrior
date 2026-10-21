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
    """One stored alert. `at` is when it was first raised (the rows are in that order);
    `count` is how many times it happened in its window."""

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
    """One channel this run has. `failing` when its newest real delivery did not get through
    (failed, expired, or retrying after a failed try); `waiting` is how many deliveries are
    still open. `enabled` is `False` for a channel the owner switched off (`EPIC-036D8`); it is
    then never `failing`, because nothing is sent there and its last delivery is old news."""

    channel_id: str
    failing: bool
    waiting: int
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class AlertHistoryReport:
    """The newest alerts first, and the state of every channel."""

    rows: tuple[AlertHistoryRow, ...]
    channels: tuple[ChannelHealth, ...]
