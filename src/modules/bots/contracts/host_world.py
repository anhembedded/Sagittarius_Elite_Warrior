"""`EPIC-047E` — everything the VPS tab knows of its host, as one value.

@details The VPS tab opens no connection to Binance (decision record 2026-10-27, D1): every fact it
shows was published by the host and carried over the bridge. This is that picture at one moment — the
bots, the facts only the host holds, what the host last read from the exchange — together with *when*
each part reached the desktop, so a screen can say how old a fact is and a disconnected tab can say
"data as of …". It is a value and never changes; the next event makes a new one.

@par A fact the host never published is `None`, not an empty value
`held` and `reads` are `None` until the host's file has been read at least once (the host is not
running the feed, or the bridge never saw the file). A query answers such a gap with
`NOT_PUBLISHED_BY_THE_HOST` and never with a default that reads like a fact (decision record D5).

@par Extension cases
  · another host document (the market file) — one more field with a `None` default here and one
    reader in the link; the queries that do not ask for it are untouched.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.exchange_reads import (
    HostExchangeReads,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_held_facts import (
    HostHeldFacts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import (
    RefusedBotFile,
)


class HostFileState(StrEnum):
    """What the bridge can say of one host file."""

    #: Read, and the host rewrote it within three of its own heartbeats.
    LIVE = "live"
    #: Read, but the host has been quiet for longer: it may have stopped. The document is the last one.
    STALE = "stale"
    #: There is no file, or none was ever readable.
    MISSING = "missing"


@dataclass(frozen=True, slots=True)
class HostFile:
    """How current one host file is, as of the moment the desktop looked."""

    state: HostFileState = HostFileState.MISSING
    #: Seconds since the host wrote it when the desktop looked (the bridge's own measure, on the host).
    age_s: float | None = None
    #: When the desktop looked, on its own clock; `age_s` plus the time since then is the age now.
    looked_at: datetime | None = None


#: What a screen says of a fact the host never published (decision record 2026-10-27, D5).
NOT_PUBLISHED_BY_THE_HOST = "not published by the host"


@dataclass(frozen=True, slots=True)
class HostWorld:
    """The bots and the host's published facts, as the desktop last heard them."""

    #: Every stored bot, oldest first, and the files the host could not read (`BotList`).
    bots: tuple[BotSnapshot, ...] = ()
    refused: tuple[RefusedBotFile, ...] = ()
    #: The facts only the running host holds (`state/host-facts.json`); `None` before it was read.
    #: Its `held_file` says whether the host still writes it: a `STALE` document is the last one of a host
    #: that may have stopped, and no query answers from it as if it were current.
    held: HostHeldFacts | None = None
    held_file: HostFile = HostFile()
    #: When the host wrote `held`, on the host's clock; `None` with it.
    held_at: datetime | None = None
    #: What the host last read from the exchange for the tab (`state/host-reads.json`), and its currency.
    reads: HostExchangeReads | None = None
    reads_file: HostFile = HostFile()
    reads_at: datetime | None = None
    #: When the last frame of any kind (an answer, an event, a heartbeat's revision) came from the host,
    #: on the desktop's clock; `None` before the first snapshot. It proves the link, not the data:
    #: a disconnected tab shows it as "data as of …", and a connected one never as how fresh a fact is.
    last_frame_at: datetime | None = None
    #: Whether the link to the host is up now.
    connected: bool = False
