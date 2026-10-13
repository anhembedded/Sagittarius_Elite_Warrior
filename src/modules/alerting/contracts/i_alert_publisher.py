"""`IAlertPublisher` — how a source hands an alert to the module (`EPIC-036A`)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert import Alert


class IAlertPublisher(ABC):
    """Cheap and non-blocking: the caller's thread records the alert and returns.
    No channel is called on it, so a failing, slow or rate-limited channel
    cannot hold a bot or the UI."""

    @abstractmethod
    def publish(self, alert: Alert) -> None:
        """Record `alert` for delivery, after dedup, grouping, inhibition and
        routing."""

    @abstractmethod
    def condition_cleared(self, dedup_key: str, at: datetime) -> None:
        """The condition behind `dedup_key` is over: send one recovery alert if
        it had been alerted and not yet recovered; otherwise nothing."""
