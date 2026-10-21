"""The words every text channel uses for an alert (`EPIC-036G`, `EPIC-036C1`).

The mark that gives the severity at a glance and the line that says what the alert is about.
A channel adds its own markup and limits around them; the words are one place.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_subject import (
    AlertSubject,
    SubjectScope,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.severity import Severity

#: The marks the owner's eye finds first on a phone.
SEVERITY_MARK = {
    Severity.CRITICAL: "\N{LARGE RED CIRCLE}",
    Severity.WARNING: "\N{LARGE ORANGE CIRCLE}",
    Severity.INFO: "\N{LARGE BLUE CIRCLE}",
}


def subject_line(subject: AlertSubject) -> str:
    if subject.scope is SubjectScope.BOT:
        name = subject.bot_name or subject.bot_id
        return f"Bot {name} ({subject.bot_kind}) · {subject.venue} {subject.symbol}".rstrip()
    if subject.scope is SubjectScope.VENUE:
        return f"Venue {subject.venue}"
    return "The app"
