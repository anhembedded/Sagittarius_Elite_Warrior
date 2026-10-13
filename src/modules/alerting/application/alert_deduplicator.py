"""A repeat of an alert inside its window updates one record (design §7)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert import Alert
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_policies import (
    NoisePolicy,
)


@dataclass(frozen=True, slots=True)
class Repeat:
    """`alert_id` is `None` while the first occurrence is still being held back
    (grouped or quiet): the repeat is absorbed, there is no record to count on."""

    alert_id: int | None


@dataclass(slots=True)
class _Seen:
    expires_at: datetime
    alert_id: int | None


class AlertDeduplicator:
    """Windows run from the first occurrence, by severity. In memory: after a
    restart a repeat is a new record, so the owner hears it twice rather than
    never (locked by `test_dedup_windows_do_not_survive_a_restart`)."""

    def __init__(self, policy: NoisePolicy) -> None:
        self._policy = policy
        self._seen: dict[str, _Seen] = {}

    def repeat_of(self, alert: Alert, now: datetime) -> Repeat | None:
        self._forget_expired(now)
        seen = self._seen.get(alert.dedup_key)
        return None if seen is None else Repeat(seen.alert_id)

    def remember(self, alert: Alert, now: datetime, alert_id: int | None) -> None:
        self._seen[alert.dedup_key] = _Seen(
            now + self._policy.dedup_window(alert.severity), alert_id
        )

    def attach(self, dedup_keys: Iterable[str], alert_id: int) -> None:
        """Point held-back occurrences at the record that finally carried them."""
        for key in dedup_keys:
            seen = self._seen.get(key)
            if seen is not None:
                seen.alert_id = alert_id

    def forget(self, dedup_keys: Iterable[str]) -> None:
        """A cleared condition starts over: its next occurrence is a new fact, not
        a repeat of one the owner was already told is over."""
        for key in dedup_keys:
            self._seen.pop(key, None)

    def _forget_expired(self, now: datetime) -> None:
        for key in [k for k, seen in self._seen.items() if seen.expires_at <= now]:
            del self._seen[key]
