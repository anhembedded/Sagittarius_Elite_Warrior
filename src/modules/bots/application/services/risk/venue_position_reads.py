"""`BOT-184` — one reading of a venue's open positions, shared by the bots of that venue.

`positionRisk` without a symbol is one request for the whole account (weight 5), yet every idle
bot read it twice a beat (its risk watch and its protective-stop check), so N bots cost 2 × N
reads a beat. The bots of one venue read the one account, so one reading serves them all: the
first bot of a beat reads, the others of the same sweep take what it read.

**What keeps a reading honest.** A reading is served only while it is younger than `max_age`
(half a beat, `SHARED_READING_MAX_AGE_SECONDS`: the whole sweep of one beat shares it, the next
beat reads again, so no watch judges on anything older than one beat, today's worst case), and
`invalidate()` drops it the moment this app sends or cancels an order on the venue
(`BotOrderGateway`), because that is what changes a position. A failed read is never kept. The
reads that *confirm* something (a close, a divergence, a start) never come from here: they ask the
account (`BotAccountReads.position`), because a confirmation must see the exchange as it is now.

One lock serialises the reads, so bots on different threads that arrive together make one request
and the late ones take its answer.

Plausible extensions, each a local change: a per-symbol reading for a venue whose positions are
read per symbol is another reader behind the same two methods.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_monotonic_clock import (
    IMonotonicClock,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.live_position import (
    LivePosition,
)


class VenuePositionReads:
    """@brief The venue's open positions, read once for the bots that ask within `max_age`."""

    def __init__(
        self,
        read: Callable[[], tuple[LivePosition, ...]],
        monotonic: IMonotonicClock,
        max_age_seconds: float,
    ) -> None:
        self._read = read
        self._monotonic = monotonic
        self._max_age = max_age_seconds
        self._lock = threading.Lock()
        self._held: tuple[LivePosition, ...] | None = None
        self._asked_at = 0.0

    def positions(self) -> tuple[LivePosition, ...]:
        """The venue's open positions: the reading in hand while it is younger than `max_age`,
        else a new read. @raise Exception whatever the read raises; nothing is kept then."""
        with self._lock:
            now = self._monotonic.seconds()
            held = self._held
            if held is not None and now - self._asked_at < self._max_age:
                return held
            self._held = None
            positions = self._read()
            # Aged from when the request was made, never from when it came back.
            self._held, self._asked_at = positions, now
            return positions

    def invalidate(self) -> None:
        """What a reading says is no longer so (an order was sent or cancelled): the next ask
        reads again."""
        with self._lock:
            self._held = None
