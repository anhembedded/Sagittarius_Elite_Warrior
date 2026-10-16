"""`EPIC-036G` — an `IAlertPublisher` that records what a source handed it.

For testing a source on its own: what it published and which conditions it
cleared, in order. A test of the whole path uses the real `AlertHub` instead.
"""

from __future__ import annotations

import threading
from datetime import datetime

from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_publisher import (
    IAlertPublisher,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert import Alert


class RecordingAlertPublisher(IAlertPublisher):
    def __init__(self) -> None:
        self.published: list[Alert] = []
        self.cleared: list[str] = []
        self._lock = threading.Lock()

    def publish(self, alert: Alert) -> None:
        with self._lock:
            self.published.append(alert)

    def condition_cleared(self, dedup_key: str, at: datetime) -> None:
        with self._lock:
            self.cleared.append(dedup_key)
