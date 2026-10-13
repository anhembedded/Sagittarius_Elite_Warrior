"""`IAlertClock` on the wall clock, in UTC."""

from __future__ import annotations

from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_clock import (
    IAlertClock,
)


class SystemAlertClock(IAlertClock):
    def now(self) -> datetime:
        return datetime.now(UTC)
