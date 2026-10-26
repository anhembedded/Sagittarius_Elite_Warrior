"""The host-facts file as one value (`EPIC-047B`, decision G7a).

The running host writes the facts only it holds in memory (`HostHeldFacts`) to
`state/host-facts.json`, and a second process (the bridge, `EPIC-047C`) reads it. Because a second
process reads it, its shape is a contract: a field is added within a version, never renamed
(`HOST_FACTS_SCHEMA`), and the encoding sits behind `IHostFactsCodec` so `EPIC-047A`'s codec can
replace the hand encoding without changing what the file holds.

@par How a reader tells a torn, a stale and a dead file apart
  · torn - the write is atomic, so a half file is never seen; a file that does not decode anyway
    (a hand edit, a disk fault) is `HostFactsUnreadableError`, and the reader keeps the last good one;
  · older - `revision` only grows, across restarts too (the host continues from the file it finds),
    so a document whose revision is not greater than the one held is ignored;
  · dead - `written_at` plus `heartbeat_s`: the host rewrites at least that often while it lives,
    so a reader judges liveness by the host's own cadence and not by its guess of it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_held_facts import (
    HostHeldFacts,
)

HOST_FACTS_SCHEMA = "sew.host-facts/1"
HOST_FACTS_FILE_NAME = "host-facts.json"

#: Seconds between two looks at the host's facts. A change reaches the file within this and the
#: time one write takes; a lease or a venue is no fill, so the 5 s of the epic's AC2 is not at stake.
FACTS_POLL_SECONDS = 2
#: The longest the file goes unwritten while the host lives: a quiet host rewrites it this often,
#: so a reader can tell a live host from a dead one (`HostFactsHeader.heartbeat_s`).
FACTS_HEARTBEAT_SECONDS = 15


class HostFactsUnreadableError(ValueError):
    """The file exists and is not a host-facts file of this schema, or cannot be read."""


@dataclass(frozen=True, slots=True)
class HostFactsHeader:
    """What a reader needs to judge a file before it reads a single fact."""

    #: Grows by one on every write, and continues from the file found at start-up.
    revision: int
    written_at: datetime
    #: The longest this host goes without writing; a reader calls the host dead after a few.
    heartbeat_s: int
    pid: int


@dataclass(frozen=True, slots=True)
class HostFactsDocument:
    header: HostFactsHeader
    facts: HostHeldFacts
