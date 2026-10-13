"""The alerting section of the host's health snapshot (`EPIC-038C`).

The one fact worth an operator's glance: is an alert stuck? Counts and an age,
read from the outbox with two short queries; no secret, no alert text.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta

from Sagittarius_Elite_Warrior.src.core.contracts.i_health_contributor import (
    DEGRADED,
    REASON_KEY,
    STATUS_KEY,
    IHealthContributor,
)
from Sagittarius_Elite_Warrior.src.core.contracts.report import JsonValue
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_clock import (
    IAlertClock,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_outbox import IOutbox

SECTION_NAME = "alerting"

#: An undelivered alert older than this means the owner is not hearing from the
#: bots: the section says it is not well.
STUCK_AFTER = timedelta(minutes=15)


class AlertingHealthContributor(IHealthContributor):
    def __init__(self, outbox: IOutbox, clock: IAlertClock) -> None:
        self._outbox = outbox
        self._clock = clock

    @property
    def name(self) -> str:
        return SECTION_NAME

    def snapshot(self) -> Mapping[str, JsonValue]:
        backlog = self._outbox.backlog(self._clock.now())
        age = backlog.oldest_age
        section: dict[str, JsonValue] = {
            "undelivered": backlog.depth,
            "oldest_undelivered_age_s": None
            if age is None
            else int(age.total_seconds()),
        }
        if age is not None and age > STUCK_AFTER:
            section[STATUS_KEY] = DEGRADED
            section[REASON_KEY] = "alerts waiting for delivery"
        return section
