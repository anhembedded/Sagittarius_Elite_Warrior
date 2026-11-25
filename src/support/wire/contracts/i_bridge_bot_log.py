"""`EPIC-047F` — a bot's own log lines, as the bridge reads them. Implemented by `operations` (`modules/operations/link.py`)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BridgeLogLine:
    seq: int
    at: str
    level: str
    text: str


@dataclass(frozen=True, slots=True)
class BridgeLogPage:
    """Lines after a cursor, oldest first, and the cursor to ask from next (the last line's `seq`, or the one given)."""

    lines: tuple[BridgeLogLine, ...]
    next_since: int


class IBridgeBotLog(ABC):
    @abstractmethod
    def read(self, bot_id: str, since: int) -> BridgeLogPage:
        """The lines of `bot_id` with `seq > since` (the newest ones when `since` is 0), bounded by the host's own limits.
        Read-only; never raises: an unknown bot, no file or an unreadable one is an empty page."""
