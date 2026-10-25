"""`BUG-270` - a position venue's bot that waits out a dead price feed under its protective stop.

A Futures bot halted for `price_feed_stale` used to cancel its ladder and close its position at
market, although a stop on the exchange covered it. Now the halt is a wait (`AWAITING_RECOVERY`,
the rule of `venue_profile.py` → `_FUTURES`) **only while a stop that the exchange shows covers the
position**: the ladder and the stop stay, nothing is closed, and the bot recovers by itself through
the Resume path when the price has stayed clear for the dwell.

This class is the one place that says when such a wait may begin, what it is, and when it must end:

  · **begin** (`halt_plain_words`): read fresh from the exchange, never from the bot's record
    (ADR 038M D4, `StopCoverageReader`). Anything but `COVERED`, an unread stop included, is a plain
    halt, which parks the bot and closes it as it always did;
  · **is** (`holds`): AWAITING_RECOVERY for `price_feed_stale` on a venue whose halt closes. A venue
    that closes nothing on a halt (Spot) never waits with its ladder: its wait is the old one;
  · **end** (`ends_with`): the stop stopped covering, could not be read for `UNREAD_BEATS_BEFORE_ENDING`
    beats in a row, or the wait outlasted `COVERED_WAIT_LIMIT` (the owner's 15 minutes, 2026-10-25).
    The end is the existing path: the plain halt, which cancels the ladder and closes the position.

Touched only on the bot's worker.
"""

from __future__ import annotations

from datetime import timedelta

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_stop_coverage import (
    StopCoverage,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_exposure_closer import (
    IExposureCloser,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_exposure_protection import (
    IExposureProtection,
)

#: How long a bot may wait with its ladder and its stop for the price to come back, before the
#: existing path closes it (owner decision, 2026-10-25, `BUG-270`). A wait that outlasts it has had
#: a position with no managed ladder for that long.
COVERED_WAIT_LIMIT = timedelta(minutes=15)

#: Beats (5 s) in a row a stop may be unreadable before the wait ends: one failed read is a blip of
#: the network the wait is for, a quarter of a minute of them is not "covered".
UNREAD_BEATS_BEFORE_ENDING = 3


class GridCoveredWait:
    """When a Grid may wait under its stop, and when that wait is over."""

    def __init__(
        self,
        context: GridRunContext,
        closer: IExposureCloser,
        protection: IExposureProtection,
    ) -> None:
        self._context = context
        self._closer = closer
        self._protection = protection
        self._unread_beats = 0

    def halt_plain_words(self) -> str:
        """Why a halt for a quiet feed must not be a wait, or `""` when it may be (the venue closes
        nothing on a halt, or a stop on the exchange covers the position)."""
        if not self._closer.closes_on_halt():
            return ""
        reading = self._protection.read_coverage()
        if reading.coverage is StopCoverage.COVERED:
            return ""
        return (
            "no stop on the exchange is read to cover its position "
            f"({reading.words}), so it does not wait: it is closed"
        )

    def holds(self) -> bool:
        """Whether the bot is in a wait that keeps its ladder and its stop."""
        return (
            self._context.state.waits_for_a_quiet_feed and self._closer.closes_on_halt()
        )

    def ends_with(self, waited_seconds: float) -> str | None:
        """What ends this beat's wait, in words, or `None` while it goes on."""
        if waited_seconds >= COVERED_WAIT_LIMIT.total_seconds():
            self._unread_beats = 0
            return (
                f"it waited {int(waited_seconds)} s under its stop, the most it may "
                f"({int(COVERED_WAIT_LIMIT.total_seconds())} s)"
            )
        reading = self._protection.read_coverage()
        if reading.coverage is StopCoverage.COVERED:
            self._unread_beats = 0
            return None
        if reading.coverage is StopCoverage.UNREAD:
            self._unread_beats += 1
            if self._unread_beats < UNREAD_BEATS_BEFORE_ENDING:
                return None
        self._unread_beats = 0
        return f"its stop no longer covers its position ({reading.words})"
