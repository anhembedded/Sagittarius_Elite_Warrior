"""`EPIC-047F` — a bot's own log lines as the VPS tab gets them from the host: the lines, the cursor, and why there are none."""

from __future__ import annotations

from dataclasses import dataclass


class BotLogUnavailableError(Exception):
    """The host's log for a bot could not be read now; `words` is a sentence the tab shows as it is."""

    def __init__(self, words: str) -> None:
        super().__init__(words)
        self.words = words


@dataclass(frozen=True, slots=True)
class BotLogLineOfTheHost:
    seq: int
    #: The moment the host wrote it, ISO 8601 with its offset.
    at: str
    level: str
    text: str


@dataclass(frozen=True, slots=True)
class BotLogChunk:
    """The lines after the cursor that was asked for, oldest first, and the cursor for the next ask."""

    lines: tuple[BotLogLineOfTheHost, ...]
    next_since: int
