"""`BOT-184` — the shared reading of each venue's positions, found by venue.

One `VenuePositionReads` per venue, made when the first bot of the venue asks and kept: the bots
of a venue are on the one account (`VenuePositionReads`). Built once by the composition and handed
to the risk watch and to every bot's gateway, so they share the same reading.
"""

from __future__ import annotations

import threading

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.risk.venue_position_reads import (
    VenuePositionReads,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.watches.bot_price_watch import (
    CHECK_EVERY_SECONDS,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_monotonic_clock import (
    IMonotonicClock,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

#: How long a reading serves the bots of a venue: half a beat, so one beat's whole sweep shares it
#: and the next beat never does.
SHARED_READING_MAX_AGE_SECONDS = CHECK_EVERY_SECONDS / 2


class SharedPositionReads:
    """@brief The venue's shared positions reading, by venue."""

    def __init__(
        self,
        ports: IVenueTradingPorts,
        monotonic: IMonotonicClock,
        max_age_seconds: float = SHARED_READING_MAX_AGE_SECONDS,
    ) -> None:
        self._ports = ports
        self._monotonic = monotonic
        self._max_age = max_age_seconds
        self._lock = threading.Lock()
        self._by_venue: dict[TradingVenue, VenuePositionReads] = {}

    def of(self, venue: TradingVenue) -> VenuePositionReads:
        with self._lock:
            reads = self._by_venue.get(venue)
            if reads is None:
                snapshot = self._ports.get(venue).account_snapshot
                reads = VenuePositionReads(
                    snapshot.open_positions, self._monotonic, self._max_age
                )
                self._by_venue[venue] = reads
            return reads
