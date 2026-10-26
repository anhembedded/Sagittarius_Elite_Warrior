"""`EPIC-047B` — the venue's facts reader, remembering what it read (decision G7a).

@details A decorator on `IVenueFacts`: it asks the inner reader exactly what and when the caller
asked, hands the caller its answer unchanged, and remembers it. The host publishes what was
remembered, so the exchange is asked no more often than before (the file adds no REST weight on
the account the bots trade on) and a published snapshot is at most as old as the last Start, Resume
or screen load that read it - `read_at` in the snapshot says how old.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.futures_facts import (
    VenueSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_latest_venue_reads import (
    ILatestVenueReads,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_venue_facts import (
    IVenueFacts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import Bot


class RecordedVenueFacts(IVenueFacts):
    def __init__(self, inner: IVenueFacts, latest: ILatestVenueReads) -> None:
        self._inner = inner
        self._latest = latest

    def read(self, bot: Bot) -> VenueSnapshot:
        snapshot = self._inner.read(bot)
        self._latest.record(bot.bot_id.value, snapshot)
        return snapshot
