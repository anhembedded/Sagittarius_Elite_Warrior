"""`EPIC-047B` — `ILatestVenueReads` in memory: one slot per bot, under a lock."""

from __future__ import annotations

import threading

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.futures_facts import (
    VenueSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_held_facts import (
    BotExchangeRead,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_latest_venue_reads import (
    ILatestVenueReads,
)


class LatestVenueReads(ILatestVenueReads):
    """Called from the threads that start, resume and select bots and from the facts writer, so
    every access takes the lock; the slots are as many as there are bots."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._latest: dict[str, VenueSnapshot] = {}

    def record(self, bot_id: str, snapshot: VenueSnapshot) -> None:
        with self._lock:
            self._latest[bot_id] = snapshot

    def latest(self) -> tuple[BotExchangeRead, ...]:
        with self._lock:
            held = dict(self._latest)
        return tuple(BotExchangeRead(bot_id, held[bot_id]) for bot_id in sorted(held))
