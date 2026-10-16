"""The typed alert: what happened, to what, how urgent (`EPIC-036A`)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_catalog import (
    severity_of,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_subject import (
    AlertSubject,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.severity import Severity


@dataclass(frozen=True, slots=True)
class Alert:
    """A channel formats this itself (an embed, Markdown); the hub never hands
    it a pre-built string.

    `dedup_key` names the *condition*: two alerts with one key are the same
    thing happening again. `recovery` marks the one message sent when the
    condition clears.
    """

    kind: AlertKind
    severity: Severity
    subject: AlertSubject
    title: str
    detail: str
    at: datetime
    dedup_key: str
    recovery: bool = False

    def __post_init__(self) -> None:
        if self.at.tzinfo is None:
            raise ValueError("An alert's time needs a timezone")
        if not self.title:
            raise ValueError("An alert needs a title")
        if not self.dedup_key:
            raise ValueError("An alert needs a dedup key")
        object.__setattr__(self, "at", self.at.astimezone(UTC))

    @classmethod
    def raised(
        cls,
        kind: AlertKind,
        subject: AlertSubject,
        title: str,
        detail: str,
        at: datetime,
        reason: str = "",
    ) -> Alert:
        """An alert at its kind's default severity, keyed by kind, subject and reason."""
        return cls(
            kind,
            severity_of(kind),
            subject,
            title,
            detail,
            at,
            cls.condition_key(kind, subject, reason),
        )

    @staticmethod
    def condition_key(kind: AlertKind, subject: AlertSubject, reason: str = "") -> str:
        """The `dedup_key` `raised` gives: what a source passes to
        `condition_cleared` to end the condition it raised."""
        return f"{kind.name}:{subject.identity}:{reason}"
