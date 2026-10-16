"""What a Discord webhook message for an alert looks like (`EPIC-036G`).

Pure functions: an `Alert` and a loudness in, the JSON body out. The skeleton
sends plain text; the embed coloured by severity and the grouped layout are
`EPIC-036C`'s, and they change this file only.

Two rules the body always keeps:
  · **no mention is ever parsed** (`allowed_mentions.parse = []`): a bot's name
    or a reason is text the owner typed or the exchange sent, and `@everyone`
    in it must not ping a server;
  · **silent is Discord's own flag** (`SUPPRESS_NOTIFICATIONS`): the message is
    delivered without a push, as N4 asks for a silent cell.
"""

from __future__ import annotations

import re

from Sagittarius_Elite_Warrior.src.core.contracts.report import JsonValue
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert import Alert
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_subject import (
    AlertSubject,
    SubjectScope,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.loudness import Loudness
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.severity import Severity

#: Discord's message flag that delivers without a notification (`1 << 12`).
SUPPRESS_NOTIFICATIONS = 4096

#: Discord refuses a message `content` longer than this.
MAX_CONTENT = 2000

#: The marks the owner's eye finds first on a phone.
_SEVERITY_MARK = {
    Severity.CRITICAL: "\N{LARGE RED CIRCLE}",
    Severity.WARNING: "\N{LARGE ORANGE CIRCLE}",
    Severity.INFO: "\N{LARGE BLUE CIRCLE}",
}

#: A webhook URL as Discord issues it: its own host (or a client channel's), the
#: API path, an id and a token. Anything else is not sent to. ASCII classes only
#: (`[0-9]`, not `\d`, which also matches other scripts' digits).
_WEBHOOK_URL = re.compile(
    r"https://(?:(?:ptb|canary)\.)?discord(?:app)?\.com/api(?:/v[0-9]+)?/webhooks/[0-9]+/[A-Za-z0-9_-]+"
)


def is_discord_webhook_url(value: str) -> bool:
    """Whether `value` is a Discord webhook URL, and so may be posted to."""
    return _WEBHOOK_URL.fullmatch(value) is not None


def discord_payload(alert: Alert, loudness: Loudness) -> dict[str, JsonValue]:
    """The JSON body of one webhook message for `alert`."""
    body: dict[str, JsonValue] = {
        "content": _content(alert),
        "allowed_mentions": {"parse": []},
    }
    if loudness is Loudness.SILENT:
        body["flags"] = SUPPRESS_NOTIFICATIONS
    return body


def _content(alert: Alert) -> str:
    head = f"{_SEVERITY_MARK[alert.severity]} **{alert.severity.name} · {alert.title}**"
    lines = [head, _subject_line(alert.subject)]
    if alert.detail:
        lines.append(alert.detail)
    lines.append(f"{alert.at:%Y-%m-%d %H:%M:%S} UTC")
    text = "\n".join(lines)
    if len(text) <= MAX_CONTENT:
        return text
    return text[: MAX_CONTENT - 1] + "\N{HORIZONTAL ELLIPSIS}"


def _subject_line(subject: AlertSubject) -> str:
    if subject.scope is SubjectScope.BOT:
        name = subject.bot_name or subject.bot_id
        return f"Bot {name} ({subject.bot_kind}) · {subject.venue} {subject.symbol}".rstrip()
    if subject.scope is SubjectScope.VENUE:
        return f"Venue {subject.venue}"
    return "The app"
