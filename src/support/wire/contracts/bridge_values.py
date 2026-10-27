"""`EPIC-047C` — the values the bridge's ports trade: a wire root's name with its value, a bot's file as read, the facts file as looked at."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


@dataclass(frozen=True, slots=True)
class Wired:
    """A contract value and the name of the wire root that carries it."""

    root: str
    value: object


@dataclass(frozen=True, slots=True)
class BotReading:
    """What one bot's file holds right now: a bot, a refusal in words, or nothing (the file is gone)."""

    bot: Wired | None = None
    refused: str = ""


class FactsState(StrEnum):
    """What the bridge can say of the host-facts file."""

    #: Read, and the host rewrote it within three of its own heartbeats.
    LIVE = "live"
    #: Read, and the host has been quiet for longer: it may have stopped.
    STALE = "stale"
    #: There is no file, or none was ever readable.
    MISSING = "missing"


@dataclass(frozen=True, slots=True)
class FactsLook:
    """The latest good host-facts file, how old it is and whether the host lives."""

    state: FactsState
    #: The file's revision; 0 without a good file.
    revision: int = 0
    #: Seconds since the host wrote it, by the bridge's own clock on the host; `None` without a file.
    age_s: float | None = None
    document: Wired | None = None
    #: Why the latest look did not move the held document ("" when it did or found it unchanged).
    problem: str = ""
