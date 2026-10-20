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

#: Telegram refuses a message longer than this. The text is measured in UTF-16 code units, the
#: unit Telegram counts entity offsets in and an upper bound on its count of characters either
#: way: an emoji is two units, so a text of 4096 code points can be 8000 units.
MAX_TEXT = 4096

#: The head and the subject line are cut to this many characters before anything else, so a
#: pathological bot name cannot leave no room for the detail (it is bounded upstream, but the
#: message must not depend on that).
_MAX_HEAD_PART = 300

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
        f"{escape(_clipped(alert.title))}</b>"
    )
    foot = f"{alert.at:%Y-%m-%d %H:%M:%S} UTC"
    fixed = [head, escape(_clipped(subject_line(alert.subject)))]
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
        if _units(joined(middle)) <= MAX_TEXT:
            low = middle
        else:
            high = middle - 1
    return joined(low)


def _clipped(text: str) -> str:
    return text if len(text) <= _MAX_HEAD_PART else text[:_MAX_HEAD_PART] + _ELLIPSIS


def _units(text: str) -> int:
    """UTF-16 code units: the largest count Telegram could mean by a message's length."""
    return len(text.encode("utf-16-le")) // 2
