"""`EPIC-047H` — what the refresher's worker holds between steps: its timings, its jobs and what it shares with the requesting thread."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_read_refresh import (
    RefreshScope,
    RefreshTarget,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.vps_refresh_costs import (
    ReadKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_weight_meter import (
    IVenueWeightMeter,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

#: Sleep when there is nothing to do, and the longest sleep: a new bot or a request is noticed within this.
IDLE_S = 5.0
#: What a refresh asked for by the tab reads: everything the tab shows for one bot.
ASKED_ROUND = (ReadKind.FACTS, ReadKind.CANDLES, ReadKind.PLANNER, ReadKind.FILLS)
#: A symbol's candles are synced at most this often, whoever asks and however many bots are on it.
CANDLES_EVERY_S = 300.0
#: A host that has just started is busy restoring, reconciling and recovering its bots; the first refresh waits this long.
STARTUP_GRACE_S = 20.0
#: The pause after a read, so two reads are never back to back.
BETWEEN_READS_S = 0.5
#: The static exchange info is read again this often (decision record D4: once at start, then daily).
STATIC_EVERY_S = 24 * 3600.0
MIN_SPACING_S = 1.0

SCOPE_OF: dict[ReadKind, RefreshScope] = {
    ReadKind.FACTS: RefreshScope.FACTS,
    ReadKind.PLANNER: RefreshScope.PLANNER,
    ReadKind.FILLS: RefreshScope.FILLS,
    ReadKind.CANDLES: RefreshScope.CANDLES,
}


class RefreshWake(threading.Event):
    """The flag that wakes the refresher's worker early (a refresh was asked for); a type of its own so the container can hold it."""


type Meters = Callable[[TradingVenue], IVenueWeightMeter | None]


@dataclass(slots=True)
class Slot:
    #: When the bot's next round begins; while its round runs, when it began.
    due_s: float
    rounds: int = 0
    #: The reads still to make in the round that is running; empty between rounds.
    queue: list[ReadKind] = field(default_factory=list)


@dataclass(slots=True)
class Read:
    at_s: float
    read_at: datetime


@dataclass(frozen=True, slots=True)
class Job:
    kind: ReadKind
    venue: TradingVenue
    bot_id: str = ""
    #: Whether the tab asked for this round (`IFactsRefreshRequests`), as against the schedule's own.
    asked: bool = False


#: The reads that give way first: when the ceiling has no room for one of these it waits its turn and the
#: facts reads of the other bots go on, so a dear fills read never stalls the whole venue.
SLOW_KINDS = frozenset({ReadKind.PLANNER, ReadKind.FILLS, ReadKind.CANDLES})


@dataclass(slots=True)
class State:
    """What the worker and the requesting thread share, under `lock`."""

    lock: threading.Lock = field(default_factory=threading.Lock)
    known: dict[str, RefreshTarget] = field(default_factory=dict)
    pending: list[str] = field(default_factory=list)
    last_read: dict[str, Read] = field(default_factory=dict)
