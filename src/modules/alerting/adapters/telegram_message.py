"""What a Telegram `sendMessage` for an alert looks like (`EPIC-036C1`).

Pure functions: a chat, an alert and a loudness in, the JSON body out.

**HTML, not MarkdownV2.** Telegram's MarkdownV2 makes eighteen characters special and a bot name
or an exchange message holds any of them; one missed escape and Telegram refuses the whole
message (400), which for an alert is a lost alert. HTML has three characters to escape
(`&`, `<`, `>`), `html.escape` does it, and the only tag the message writes is its own bold head.

Two rules the body always keeps:
  - **text an alert carries is never markup**: every piece is escaped before it is put in;
  - **silent is Telegram's own flag** (`disable_notification`): delivered without a push, as N4
    asks of a silent cell.
"""

from __future__ import annotations

from html import escape

from Sagittarius_Elite_Warrior.src.core.contracts.report import JsonValue
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.alert_text import (
    SEVERITY_MARK,
    subject_line,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert import Alert
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.loudness import Loudness

#: Telegram refuses a message longer than this, counted after parsing; the escaped text is
#: never longer than the count that matters, so it is the safe bound to keep under.
MAX_TEXT = 4096

_ELLIPSIS = "\N{HORIZONTAL ELLIPSIS}"


def telegram_payload(
    chat_id: str, alert: Alert, loudness: Loudness
) -> dict[str, JsonValue]:
    """The JSON body of one `sendMessage` for `alert`."""
    return {
        "chat_id": chat_id,
        "text": _text(alert),
        "parse_mode": "HTML",
        "disable_notification": loudness is Loudness.SILENT,
    }


def _text(alert: Alert) -> str:
    head = (
        f"<b>{SEVERITY_MARK[alert.severity]} {escape(alert.severity.name)} · "
        f"{escape(alert.title)}</b>"
    )
    foot = f"{alert.at:%Y-%m-%d %H:%M:%S} UTC"
    fixed = [head, escape(subject_line(alert.subject))]
    return _fitting(fixed, alert.detail, foot)


def _fitting(fixed: list[str], detail: str, foot: str) -> str:
    """Join the pieces with the longest detail that fits. The *raw* detail is cut and escaped
    afterwards, so a cut never leaves half an entity (`&am`); the length grows with the
    number of characters kept, so the largest that fits is found by bisection."""

    def joined(keep: int) -> str:
        shown = detail if keep == len(detail) else detail[:keep] + _ELLIPSIS
        return "\n".join([*fixed, *([escape(shown)] if shown else []), foot])

    low, high = 0, len(detail)
    while low < high:
        middle = (low + high + 1) // 2
        if len(joined(middle)) <= MAX_TEXT:
            low = middle
        else:
            high = middle - 1
    return joined(low)
