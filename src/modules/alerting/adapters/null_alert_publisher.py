"""`IAlertPublisher` for a copy that must not write.

A read-only copy of the data root (`EPIC-035H`) neither opens the outbox nor
starts a lane: it would write the file of the host it is looking at. Alerts it is
handed are logged at DEBUG and dropped; the writable copy owns alerting.
"""

from __future__ import annotations

import logging
from datetime import datetime

from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_publisher import (
    IAlertPublisher,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert import Alert

logger = logging.getLogger("App.Alerting")


class NullAlertPublisher(IAlertPublisher):
    def publish(self, alert: Alert) -> None:
        logger.debug("[alert-skipped] read-only copy, not sending %s", alert.dedup_key)

    def condition_cleared(self, dedup_key: str, at: datetime) -> None:
        logger.debug("[alert-skipped] read-only copy, ignoring clear of %s", dedup_key)
