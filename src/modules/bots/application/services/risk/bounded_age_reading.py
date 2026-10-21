"""`BOT-184`, `BOT-221` — one reading of something an exchange account holds, shared while it is fresh.

The mechanism both shared readings of the bots (a venue's open positions, a symbol's mark price)
stand on, so the rules that keep a shared reading honest are written once.

**What keeps a reading honest.** A reading is served only while it is younger than `max_age` (half
a beat for the bots' watches: the whole sweep of one beat shares it, the next beat reads again, so
no watch judges on anything older than one beat, today's worst case), and `invalidate()` drops it
the moment this app sends or cancels an order, or hears a fill, that changes what it says. A read
that was in flight when `invalidate()` came is returned to the caller that asked and never kept:
each read carries the generation it began in, and is stored only if no invalidation has come
since. A failed read is never kept. A read that *confirms* something never comes from here.

**Two locks, for two jobs.** `_read_lock` serialises the reads, so callers on different threads
that arrive together make one request and the late ones take its answer; it is held across the
network call. `_state_lock` guards the reading and its generation and is held for a few
instructions, so `invalidate()` never waits behind a read: an order is never delayed by another
bot's slow read.

Plausible extensions, each a local change: a reading of another account fact (open orders of a
symbol) is one more instance with its own read; none is built, because the one open-orders read a
bot makes in a beat has no second reader to share it with (`BOT-221`).
"""

from __future__ import annotations

import threading
from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_monotonic_clock import (
    IMonotonicClock,
)


class BoundedAgeReading[T]:
    """@brief A value read from the exchange, served to whoever asks within `max_age`."""

    def __init__(
        self,
        read: Callable[[], T],
        monotonic: IMonotonicClock,
        max_age_seconds: float,
    ) -> None:
        self._read = read
        self._monotonic = monotonic
        self._max_age = max_age_seconds
        self._read_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._held: tuple[T] | None = None
        self._asked_at = 0.0
        self._generation = 0

    def current(self) -> T:
        """The reading in hand while it is younger than `max_age`, else a new read.
        @raise Exception whatever the read raises; nothing is kept then."""
        with self._read_lock:
            now = self._monotonic.seconds()
            with self._state_lock:
                held = self._held
                if held is not None and now - self._asked_at < self._max_age:
                    return held[0]
                generation = self._generation
            value = self._read()
            with self._state_lock:
                # Kept only if nothing changed the account while it was being read; aged from
                # when the request was made, never from when it came back.
                if self._generation == generation:
                    self._held, self._asked_at = (value,), now
            return value

    def invalidate(self) -> None:
        """What the reading says is no longer so (an order, a cancel or a fill): the next ask
        reads again, and a read in flight is not kept. Never waits for a read."""
        with self._state_lock:
            self._held = None
            self._generation += 1
