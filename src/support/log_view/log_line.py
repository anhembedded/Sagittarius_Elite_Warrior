"""The head of a log record, read back from the plain line the app writes.

The pattern is the fixed-field format `%(asctime)s - %(name)s - %(levelname)s -
%(message)s` (`logging-rule.md` §8, `Docs/OPERATIONS/LOGGING.md` §3).
`test_the_viewer_reads_what_the_app_writes.py` formats a record with the format
string the application really configures and parses it back, so the pattern and
the format cannot drift apart unseen.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

_HEAD = re.compile(
    r"(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) - "
    r"(?P<logger>\S+) - "
    r"(?P<level>[A-Za-z]+(?: \d+)?) - "
    r"(?P<message>.*)"
)
_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S,%f"

#: `logging-rule.md` §6: TRACE is level 5, below DEBUG.
LEVEL_NUMBERS = {
    "TRACE": 5,
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
    "CRITICAL": 50,
}
_NUMBERED = re.compile(r"Level (\d+)")


@dataclass(frozen=True, slots=True)
class LogHead:
    """One record's first line, cut at the three ` - ` separators."""

    body: str
    timestamp: str
    logger: str
    level: str
    message: str
    logger_start: int
    level_start: int
    message_start: int

    def moment(self) -> datetime | None:
        """The record's time (the process wrote it in its local time), or `None`."""
        try:
            return datetime.strptime(self.timestamp, _TIMESTAMP_FORMAT).astimezone()
        except ValueError:
            return None

    def level_number(self) -> int | None:
        return level_number(self.level)


def level_number(name: str) -> int | None:
    """The number of a level name (`WARNING` -> 30, `Level 7` -> 7); `None` if unknown."""
    known = LEVEL_NUMBERS.get(name.upper())
    if known is not None:
        return known
    numbered = _NUMBERED.fullmatch(name)
    return int(numbered.group(1)) if numbered else None


def parse_head(body: str) -> LogHead | None:
    """The head of a record line, or `None` for any other line (never raises)."""
    found = _HEAD.fullmatch(body)
    if found is None:
        return None
    return LogHead(
        body=body,
        timestamp=found.group("ts"),
        logger=found.group("logger"),
        level=found.group("level"),
        message=found.group("message"),
        logger_start=found.start("logger"),
        level_start=found.start("level"),
        message_start=found.start("message"),
    )
