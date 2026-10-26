"""`EPIC-047B` — port: the last snapshot each bot's readiness read took, as the host's own readers took it.

@details Written by the reader that already asks the exchange (`RecordedVenueFacts`), read by the
host's facts. It is a memory of reads that happened, never a request for one: asking this port
costs the exchange nothing.

@par Extension cases
  · an age limit on what is carried - one filter in `latest()`; today the snapshot's own `read_at`
    lets a reader judge its age.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.futures_facts import (
    VenueSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_held_facts import (
    BotExchangeRead,
)


class ILatestVenueReads(ABC):
    @abstractmethod
    def record(self, bot_id: str, snapshot: VenueSnapshot) -> None:
        """Remember `snapshot` as the latest read for `bot_id`. Never raises, never blocks."""

    @abstractmethod
    def latest(self) -> tuple[BotExchangeRead, ...]:
        """The latest read of every bot that has one, in bot-id order."""
