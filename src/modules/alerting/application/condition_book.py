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
        #: group key -> member keys not yet cleared; member key -> its group key.
        self._members: dict[str, set[str]] = {}
        self._group_of: dict[str, str] = {}

    def open(self, alert: Alert, now: datetime) -> None:
        """Remember `alert` as a live condition: WARNING and CRITICAL only; a
        recovery or an INFO is not a condition that clears."""
        if alert.recovery or alert.severity < Severity.WARNING:
            return
        self._open.pop(alert.dedup_key, None)
        self._open[alert.dedup_key] = _Open(alert, now)
        while len(self._open) > MAX_OPEN:
            self._drop(next(iter(self._open)))

    def adopt(self, group_key: str, member_keys: tuple[str, ...]) -> None:
        """`group_key` stands for `member_keys`: clearing the last of them clears
        it. A source clears the condition it raised (a bot's feed), never the
        group the hub made of many."""
        if group_key not in self._open or group_key in member_keys:
            return
        for key in member_keys:
            earlier = self._group_of.get(key)
            if earlier is not None and earlier != group_key:
                self._leave(earlier, key)
            self._group_of[key] = group_key
        self._members[group_key] = set(member_keys)

    def close(self, dedup_key: str) -> Alert | None:
        """The condition cleared: the alert that stood for it, once. A member of
        a group answers only when it is the last one."""
        group_key = self._group_of.get(dedup_key)
        if group_key is not None:
            self._leave(group_key, dedup_key)
            if group_key in self._members:
                return None
            dedup_key = group_key
        self._suppressed.pop(dedup_key, None)
        opened = self._open.pop(dedup_key, None)
        return None if opened is None else opened.alert

    def _leave(self, group_key: str, member_key: str) -> None:
        self._group_of.pop(member_key, None)
        members = self._members.get(group_key)
        if members is None:
            return
        members.discard(member_key)
        if not members:
            del self._members[group_key]

    def _drop(self, dedup_key: str) -> None:
        del self._open[dedup_key]
        self._suppressed.pop(dedup_key, None)
        for member in self._members.pop(dedup_key, set()):
            self._group_of.pop(member, None)

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
