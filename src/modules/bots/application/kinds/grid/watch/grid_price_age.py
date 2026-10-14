"""`EPIC-035A` — how long a running Grid has gone without hearing its price.

Held in the bot's run context and touched only on the bot's worker: a tick
(`note_tick`) and the periodic age check (`stale_detail`) are both tasks on the
bot's queue, so a tick queued before a check is counted before it, and a long
placing task cannot make a healthy feed look quiet.

Two limits, one clock (`IMonotonicClock`):

  · **before a tick since it was armed** the bot waits `PRICE_START_GRACE_SECONDS`
    from the moment it was armed: a bounded wait for the stream to open;
  · **after it**, `PRICE_STALE_AFTER_SECONDS` from the last tick.

**Armed** means "the bot began to depend on its price". It is armed when built,
at each check made while the bot is in a state a quiet feed does not halt
(HALTED, ERROR, STOPPING), and when it halts for a quiet feed. So a resume,
however long the bot sat HALTED, gets a fresh bounded wait for its first tick
instead of being halted again by the next check, before a new tick can arrive.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_monotonic_clock import (
    IMonotonicClock,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.price_freshness import (
    PRICE_STALE_AFTER_SECONDS,
    PRICE_START_GRACE_SECONDS,
    price_is_stale,
)


class GridPriceAge:
    """The last tick's age on a monotonic clock, and the verdict on it."""

    def __init__(self, clock: IMonotonicClock) -> None:
        self._clock = clock
        self._armed_at = clock.seconds()
        self._last_tick_at: float | None = None

    def note_tick(self) -> None:
        self._last_tick_at = self._clock.seconds()

    def arm(self) -> None:
        """The bot depends on its price from now: a tick heard before this no
        longer counts, and the first one is awaited for the grace again."""
        self._armed_at = self._clock.seconds()

    def stale_detail(self) -> str | None:
        """What to tell the user when the feed is quiet too long, else `None`."""
        now = self._clock.seconds()
        if self._last_tick_at is None or self._last_tick_at < self._armed_at:
            if price_is_stale(self._armed_at, now, PRICE_START_GRACE_SECONDS):
                return (
                    f"no tick {now - self._armed_at:.0f} s after the bot began to "
                    f"depend on its price; one is due within "
                    f"{PRICE_START_GRACE_SECONDS:.0f} s"
                )
            return None
        if price_is_stale(self._last_tick_at, now, PRICE_STALE_AFTER_SECONDS):
            return (
                f"last tick {now - self._last_tick_at:.0f} s ago; the limit is "
                f"{PRICE_STALE_AFTER_SECONDS:.0f} s"
            )
        return None
