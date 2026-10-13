"""Quiet hours: INFO and WARNING wait, CRITICAL never does (design §7)."""

from __future__ import annotations

from datetime import datetime

from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert import Alert
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_settings import (
    AlertSettings,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_subject import (
    AlertSubject,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.severity import Severity

#: The summary lists this many held alerts and counts the rest.
MAX_LISTED = 20

#: Held alerts are kept for the summary up to this many; older ones fall off the
#: list (they stay in the history, recorded when they were held).
MAX_HELD = 500


class QuietHoursHold:
    def __init__(self) -> None:
        self._held: list[Alert] = []

    @staticmethod
    def holds(alert: Alert, settings: AlertSettings, now: datetime) -> bool:
        quiet = settings.quiet_hours
        return (
            quiet is not None
            and alert.severity < Severity.CRITICAL
            and quiet.contains(now)
        )

    def hold(self, alert: Alert) -> None:
        self._held.append(alert)
        del self._held[:-MAX_HELD]

    def release(self, settings: AlertSettings, now: datetime) -> Alert | None:
        """One summary of everything held, once the period is over."""
        quiet = settings.quiet_hours
        if not self._held or (quiet is not None and quiet.contains(now)):
            return None
        held, self._held = self._held, []
        lines = [
            f"- {alert.at:%H:%M} {alert.severity.name.lower()} {alert.title}"
            for alert in held[:MAX_LISTED]
        ]
        if len(held) > MAX_LISTED:
            lines.append(f"... and {len(held) - MAX_LISTED} more")
        return Alert.raised(
            AlertKind.DAILY_SUMMARY,
            AlertSubject.app(),
            f"{len(held)} alerts held during quiet hours",
            "\n".join(lines),
            now,
            reason=now.isoformat(),
        )
