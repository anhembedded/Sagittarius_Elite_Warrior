"""Which records `$M logs` shows: level and above, one bot, one tag, since a time."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from Sagittarius_Elite_Warrior.src.support.log_view.log_line import (
    LEVEL_NUMBERS,
    LogHead,
)


class FilterError(ValueError):
    """A filter value the operator typed is not understood."""


_RELATIVE = re.compile(r"(\d+)\s*([smhdw])", re.IGNORECASE)
_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}


@dataclass(frozen=True, slots=True)
class LogFilter:
    min_level: int | None = None
    bot: str | None = None
    tag: str | None = None
    since: datetime | None = None

    @property
    def is_empty(self) -> bool:
        return (
            self.min_level is None
            and self.bot is None
            and self.tag is None
            and self.since is None
        )

    def accepts(self, head: LogHead) -> bool:
        return (
            self._level_ok(head)
            and self._bot_ok(head)
            and self._tag_ok(head)
            and self._since_ok(head)
        )

    def _level_ok(self, head: LogHead) -> bool:
        if self.min_level is None:
            return True
        number = head.level_number()
        return number is None or number >= self.min_level

    def _bot_ok(self, head: LogHead) -> bool:
        if self.bot is None:
            return True
        return re.search(rf"\b{re.escape(self.bot)}\b", head.message) is not None

    def _tag_ok(self, head: LogHead) -> bool:
        if self.tag is None:
            return True
        return f"[{self.tag}]" in head.message

    def _since_ok(self, head: LogHead) -> bool:
        if self.since is None:
            return True
        moment = head.moment()
        return moment is not None and moment >= self.since


def parse_level(text: str) -> int:
    """`warning`, `WARN`, `error` ... to the level's number."""
    name = text.strip().upper()
    name = "WARNING" if name == "WARN" else name
    if name not in LEVEL_NUMBERS:
        known = ", ".join(n.lower() for n in LEVEL_NUMBERS)
        raise FilterError(f"unknown level {text!r}; use one of: {known}")
    return LEVEL_NUMBERS[name]


def parse_tag(text: str) -> str:
    """`reduce-only-refused` or `[reduce-only-refused]` to the bare name."""
    return text.strip().strip("[]")


def parse_since(text: str, now: datetime) -> datetime:
    """`2h`, `1d12h`, `today`, `yesterday` or an ISO time (read as local), as an aware time."""
    value = text.strip()
    word = value.lower()
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if word == "today":
        return midnight
    if word == "yesterday":
        return midnight - timedelta(days=1)
    parts = _RELATIVE.findall(value)
    if parts and "".join(f"{n}{u}" for n, u in parts) == re.sub(r"\s+", "", value):
        seconds = sum(int(n) * _UNIT_SECONDS[u.lower()] for n, u in parts)
        return now - timedelta(seconds=seconds)
    try:
        stamp = datetime.fromisoformat(value)
    except ValueError as error:
        raise FilterError(
            f"cannot read {text!r} as a time; use 2h, 30m, 1d, today, yesterday "
            "or 2026-10-20T14:30"
        ) from error
    return stamp.astimezone()
