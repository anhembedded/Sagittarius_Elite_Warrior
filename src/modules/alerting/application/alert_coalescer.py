"""Many bots, one incident, one message (design §7).

Alerts of one kind and one venue that arrive within a window leave as a single
grouped alert listing the bots. A lone alert leaves unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert import Alert
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_catalog import label_of
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_policies import (
    NoisePolicy,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_subject import (
    AlertSubject,
    SubjectScope,
)

#: Kinds a network drop raises once per bot. A new such kind is one line here.
COALESCED_KINDS = frozenset({AlertKind.PRICE_FEED_STALE})

#: A grouped message lists this many bots and then counts the rest.
MAX_LISTED = 20


@dataclass(frozen=True, slots=True)
class CoalescedGroup:
    """What leaves the window and the dedup keys of the alerts it stands for."""

    alert: Alert
    member_keys: tuple[str, ...]


@dataclass(slots=True)
class _Window:
    opened_at: datetime
    members: list[Alert] = field(default_factory=list)


class AlertCoalescer:
    def __init__(self, policy: NoisePolicy) -> None:
        self._policy = policy
        self._windows: dict[tuple[AlertKind, str], _Window] = {}

    @staticmethod
    def wants(alert: Alert) -> bool:
        subject = alert.subject
        return (
            alert.kind in COALESCED_KINDS
            and subject.scope is SubjectScope.BOT
            and bool(subject.venue)
        )

    def add(self, alert: Alert, now: datetime) -> None:
        window = self._windows.setdefault(
            (alert.kind, alert.subject.venue), _Window(now)
        )
        window.members.append(alert)

    def discard(self, dedup_key: str) -> bool:
        """Forget a held alert whose condition cleared before it was sent."""
        for key, window in list(self._windows.items()):
            kept = [a for a in window.members if a.dedup_key != dedup_key]
            if len(kept) == len(window.members):
                continue
            if kept:
                window.members = kept
            else:
                del self._windows[key]
            return True
        return False

    def take_due(self, now: datetime) -> list[CoalescedGroup]:
        due = [
            key
            for key, window in self._windows.items()
            if now - window.opened_at >= self._policy.coalesce_window
        ]
        return [self._group(self._windows.pop(key), now) for key in due]

    @staticmethod
    def _group(window: _Window, now: datetime) -> CoalescedGroup:
        members = window.members
        keys = tuple(alert.dedup_key for alert in members)
        if len(members) == 1:
            return CoalescedGroup(members[0], keys)
        first = members[0]
        venue = first.subject.venue
        ordered = sorted(members, key=lambda alert: alert.subject.bot_name)
        lines = [
            f"- {alert.subject.bot_name} ({alert.subject.symbol})"
            for alert in ordered[:MAX_LISTED]
        ]
        if len(ordered) > MAX_LISTED:
            lines.append(f"... and {len(ordered) - MAX_LISTED} more")
        grouped = Alert(
            first.kind,
            max(alert.severity for alert in members),
            AlertSubject.venue_wide(venue),
            f"{label_of(first.kind)} on {venue}: {len(members)} bots",
            "\n".join(lines),
            now,
            f"{first.kind.name}:venue={venue}:grouped",
        )
        return CoalescedGroup(grouped, keys)
