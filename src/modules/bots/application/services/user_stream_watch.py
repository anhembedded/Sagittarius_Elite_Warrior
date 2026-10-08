"""`EPIC-035B` — what the bots module does about the user-data stream's health.

The stream is the only source of fills. Trading publishes where it is
(`UserStreamHealthEvent`); this service turns that into three guarantees for
every bot on the venue, without importing the adapter:

  1. **A reconnect catches up.** `CONNECTED` → each executor reconciles its
     ladder against the exchange's open orders and trade history, so a fill the
     stream missed in the gap places its counter order.
  2. **A connected stream is re-checked periodically**, because a stream can
     look connected and still have lost an event: every `reconcile_every`.
  3. **A stream down too long halts the bots.** Not connected for longer than
     `down_limit`: every executor halts with `USER_STREAM_DOWN` and its ladder
     is taken off, since no fill can be seen. The watch repeats this each pass
     while the outage lasts, so a bot that was STARTING (not yet halt-able) is
     caught once it runs.

A stream that returns does not resume a halted bot: `CONNECTED` only asks
executors to reconcile, and a halted one ignores it (`GridStreamGap`).

Time is the bot clock (`IBotClock`), moved by tests; the heartbeat that calls
`check()` is `ThreadPeriodicTimer`. Nothing here sleeps.

@par Extension cases (`architecture-rule.md` §7.2.1)
  · alerting an absent owner (`EPIC-035K`) subscribes one more handler to the
    same event, or reads the halt it causes; no change here;
  · sleep detection (`EPIC-035I`) calls `check()` after a wake and compares
    the clock jump; no change here;
  · per-venue limits are a dict of `UserStreamLimits` instead of one value.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_executors import (
    BotExecutors,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_clock import IBotClock
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.user_stream_health_event import (
    UserStreamHealthEvent,
    UserStreamState,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

logger = logging.getLogger("App.Bots.UserStream")


@dataclass(frozen=True, slots=True)
class UserStreamLimits:
    """The three durations of the user-stream rules, named once."""

    #: A stream not connected for longer than this halts the bots on its venue.
    #: Two minutes rides out the routine 24 h cut and a brief outage (the
    #: supervisor reconnects within seconds) while a bot never trades blind for
    #: long enough to matter on a grid whose levels are percent apart.
    down_limit: timedelta = timedelta(seconds=120)
    #: A connected stream is reconciled this often. Five minutes costs one open-
    #: orders read and one history read per bot, a small share of the REST
    #: weight budget (`EPIC-035D`), and bounds how long a lost event can hide.
    reconcile_every: timedelta = timedelta(seconds=300)
    #: How often the heartbeat calls `check()`; the precision of the two above.
    check_every: timedelta = timedelta(seconds=15)


DEFAULT_USER_STREAM_LIMITS = UserStreamLimits()


class UserStreamWatch:
    """Reacts to a venue's stream health: catch up, re-check, halt."""

    def __init__(
        self,
        executors: BotExecutors,
        clock: IBotClock,
        limits: UserStreamLimits = DEFAULT_USER_STREAM_LIMITS,
    ) -> None:
        self._executors = executors
        self._clock = clock
        self._limits = limits
        self._lock = threading.Lock()
        #: Venue -> when its current outage began.
        self._down_since: dict[TradingVenue, datetime] = {}
        #: Venue -> when its connected stream was last reconciled.
        self._reconciled_at: dict[TradingVenue, datetime] = {}

    @property
    def limits(self) -> UserStreamLimits:
        return self._limits

    def on_health(self, event: UserStreamHealthEvent) -> None:
        """Runs on the stream's thread: records, posts to the executors, returns."""
        venue = event.venue
        with self._lock:
            if event.state is UserStreamState.CONNECTED:
                self._down_since.pop(venue, None)
                self._reconciled_at[venue] = self._clock.now()
            elif event.state is UserStreamState.STOPPED:
                self._down_since.pop(venue, None)
                self._reconciled_at.pop(venue, None)
            else:
                self._down_since.setdefault(venue, event.since)
                self._reconciled_at.pop(venue, None)
        if event.state is UserStreamState.CONNECTED:
            logger.info("%s user stream connected; catching its bots up", venue.value)
            self._reconcile(venue)

    def check(self) -> None:
        """One heartbeat: halt what has been blind too long, re-check what is due."""
        now = self._clock.now()
        with self._lock:
            overdue = {
                venue: now - since
                for venue, since in self._down_since.items()
                if now - since > self._limits.down_limit
            }
            due = [
                venue
                for venue, at in self._reconciled_at.items()
                if now - at >= self._limits.reconcile_every
            ]
            for venue in due:
                self._reconciled_at[venue] = now
        for venue, down_for in overdue.items():
            self._halt(venue, down_for)
        for venue in due:
            self._reconcile(venue)

    def _reconcile(self, venue: TradingVenue) -> None:
        for executor in self._executors.on_venue(venue):
            executor.reconcile_after_gap()

    def _halt(self, venue: TradingVenue, down_for: timedelta) -> None:
        logger.warning(
            "%s user stream down for %d s; halting its bots",
            venue.value,
            int(down_for.total_seconds()),
        )
        for executor in self._executors.on_venue(venue):
            executor.halt_user_stream_down(down_for)
