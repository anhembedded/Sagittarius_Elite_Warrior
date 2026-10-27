"""`EPIC-047H` — port: ask the host to read one bot's exchange facts now (decision record 2026-10-27, D4).

@details The on-demand half of the refresh. A request is *queued*, never run on the caller's thread:
the caller is the host's control poller, and a stop must never wait behind a read of the exchange.
The refresher's worker takes it at its next step, inside the same weight ceiling as the scheduled
reads. A bot read less than `ON_DEMAND_MIN_INTERVAL_S` ago is not read again: the answer says when it was.

@par Extension cases
  · a request for a venue's static info - one more method and one more answer, the queue is the same.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

#: The least time between two reads of one bot's facts, scheduled or asked for.
ON_DEMAND_MIN_INTERVAL_S = 30


class RefreshRequestVerdict(Enum):
    #: The worker will read the bot at its next step.
    QUEUED = "queued"
    #: Read less than `ON_DEMAND_MIN_INTERVAL_S` ago; `read_at` says when.
    ALREADY_FRESH = "already_fresh"
    #: The host's refresh is off (`operations.vps_facts_refresh_interval_s` is 0).
    OFF = "off"
    #: No stored bot has that id, or its venue is not enabled.
    UNKNOWN_BOT = "unknown_bot"


@dataclass(frozen=True, slots=True)
class RefreshRequestAnswer:
    verdict: RefreshRequestVerdict
    #: When the bot's facts were last read; set for `ALREADY_FRESH`, and for `QUEUED` when an older read exists.
    read_at: datetime | None = None


class IFactsRefreshRequests(ABC):
    @abstractmethod
    def request(self, bot_id: str) -> RefreshRequestAnswer:
        """Never blocks on the exchange, never raises."""
