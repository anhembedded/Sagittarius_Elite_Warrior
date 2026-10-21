"""`IAlertHistory` — the question the Alerts screen asks (`EPIC-036D2`).

A read model beside the outbox, not a second store: the screen needs what was sent and
whether a channel is failing, in words a table can show, and it must not learn the outbox's
records. Reads storage, so a caller runs it off the UI thread.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.alert_history_report import (
    AlertHistoryReport,
)


class IAlertHistory(ABC):
    @abstractmethod
    def read(self, limit: int) -> AlertHistoryReport:
        """The newest `limit` alerts with their deliveries, and every channel's health."""
