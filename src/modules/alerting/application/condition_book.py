"""The conditions currently alerted, for inhibition and recovery (design §7)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert import Alert
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_policies import (
    NoisePolicy,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_subject import (
    SubjectScope,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.severity import Severity

#: inhibited kind -> the venue-wide kind whose presence hides it. A new pair is
#: one line here.
INHIBITED_BY = {AlertKind.PRICE_FEED_STALE: AlertKind.USER_STREAM_DOWN}

#: A source that never clears its conditions cannot grow this without bound.
MAX_OPEN = 1000


@dataclass(frozen=True, slots=True)
class _Open:
    alert: Alert
    opened_at: datetime


class ConditionBook:
    """In memory, like the dedup windows: after a restart nothing is inhibited
    and nothing recovers until the source raises the condition again."""

    def __init__(self, policy: NoisePolicy) -> None:
        self._policy = policy
        self._open: dict[str, _Open] = {}
        self._suppressed: dict[str, int] = {}

    def open(self, alert: Alert, now: datetime) -> None:
        """Remember `alert` as a live condition: WARNING and CRITICAL only; a
        recovery or an INFO is not a condition that clears."""
        if alert.recovery or alert.severity < Severity.WARNING:
            return
        self._open.pop(alert.dedup_key, None)
        self._open[alert.dedup_key] = _Open(alert, now)
        while len(self._open) > MAX_OPEN:
            oldest = next(iter(self._open))
            del self._open[oldest]
            self._suppressed.pop(oldest, None)

    def close(self, dedup_key: str) -> Alert | None:
        """The condition cleared: the alert that raised it, once."""
        self._suppressed.pop(dedup_key, None)
        opened = self._open.pop(dedup_key, None)
        return None if opened is None else opened.alert

    def inhibitor_of(self, alert: Alert, now: datetime) -> Alert | None:
        """The live venue-wide alert hiding `alert`, if any."""
        inhibitor_kind = INHIBITED_BY.get(alert.kind)
        if inhibitor_kind is None:
            return None
        for opened in self._open.values():
            candidate = opened.alert
            if (
                candidate.kind is inhibitor_kind
                and candidate.subject.scope is SubjectScope.VENUE
                and candidate.subject.venue == alert.subject.venue
                and now - opened.opened_at < self._policy.inhibition_ttl
            ):
                return candidate
        return None

    def count_suppressed(self, inhibitor_key: str) -> None:
        self._suppressed[inhibitor_key] = self._suppressed.get(inhibitor_key, 0) + 1

    def suppressed_count(self, inhibitor_key: str) -> int:
        return self._suppressed.get(inhibitor_key, 0)
