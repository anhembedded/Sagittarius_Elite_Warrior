"""`BOT-184` — one reading of a venue's open positions, shared by the bots of that venue.

`positionRisk` without a symbol is one request for the whole account (weight 5), yet every idle
bot read it twice a beat (its risk watch and its protective-stop check), so N bots cost 2 × N
reads a beat. The bots of one venue read the one account, so one reading serves them all: the
first bot of a beat reads, the others of the same sweep take what it read.

**What keeps a reading honest** is `BoundedAgeReading` (its bound, its invalidation, its
generation, its two locks). The reads that *confirm* something (a close, a divergence, a start,
whether a stop that left the open list ran) never come from here: they ask the account
(`BotAccountReads.position`), because a confirmation must see the exchange as it is now.

Plausible extensions, each a local change: a per-symbol reading for a venue whose positions are
read per symbol is another reader behind the same two methods.
"""

from __future__ import annotations

from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.risk.bounded_age_reading import (
    BoundedAgeReading,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_monotonic_clock import (
    IMonotonicClock,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.live_position import (
    LivePosition,
)


class VenuePositionReads(BoundedAgeReading[tuple[LivePosition, ...]]):
    """@brief The venue's open positions, read once for the bots that ask within `max_age`."""

    def __init__(
        self,
        read: Callable[[], tuple[LivePosition, ...]],
        monotonic: IMonotonicClock,
        max_age_seconds: float,
    ) -> None:
        super().__init__(read, monotonic, max_age_seconds)

    def positions(self) -> tuple[LivePosition, ...]:
        """The venue's open positions: the reading in hand while it is younger than `max_age`,
        else a new read. @raise Exception whatever the read raises; nothing is kept then."""
        return self.current()
