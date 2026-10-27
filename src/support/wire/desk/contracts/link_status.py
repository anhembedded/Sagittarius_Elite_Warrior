"""`EPIC-047D` — what the tab is told about the link: a state, the sentence, and how old the data is."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum


class LinkState(StrEnum):
    IDLE = "idle"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class LinkStatus:
    state: LinkState
    words: str
    #: When the data on screen was last true (UTC), or `None` before any arrived.
    data_as_of: datetime | None = None
    attempt: int = 0


def disconnected_words(since: datetime | None) -> str:
    """The sentence the tab shows while it holds the last data it read (AC6)."""
    if since is None:
        return "disconnected, no data yet"
    return f"disconnected, data as of {since.astimezone(UTC):%H:%M:%S} UTC"
