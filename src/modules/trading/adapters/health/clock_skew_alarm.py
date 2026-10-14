"""The alarm for a clock that drifts during a run (`BUG-209`).

The pre-flight judges the clock once, before the run (`ClockSkewCheck`); after that the
only trace of drift was `skew_ms` on the INFO health line, which nobody greps for. A clock
that reaches 1000 ms makes every signed request fail with `-1021`, so a bot trading on a
drifting host halts with an order error and the cause is nowhere in the journal.

The alarm uses the pre-flight's own thresholds, so one number decides both: above
`WARN_ABOVE_MS` it logs a WARNING, at `FAIL_AT_MS` an ERROR, and when the clock is back
under the warn line an INFO. It logs the **change of level**, once per venue and level, not
each measurement (`logging-rule.md` §6: a probe runs every health interval). A measurement
that found nothing (`None`) changes nothing: an exchange that does not answer says nothing
about the clock, and the probe's own failure line covers a probe that raised.
"""

from __future__ import annotations

import logging
from enum import Enum

from Sagittarius_Elite_Warrior.src.modules.trading.adapters.preflight.clock_skew_check import (
    FAIL_AT_MS,
    WARN_ABOVE_MS,
)

logger = logging.getLogger("App.Trading.ClockSkew")


class _SkewLevel(Enum):
    OK = 0
    DRIFTING = 1
    BEYOND_LIMIT = 2


def _level_of(skew_ms: int) -> _SkewLevel:
    size = abs(skew_ms)
    if size >= FAIL_AT_MS:
        return _SkewLevel.BEYOND_LIMIT
    if size > WARN_ABOVE_MS:
        return _SkewLevel.DRIFTING
    return _SkewLevel.OK


class ClockSkewAlarm:
    """Logs when a venue's measured skew crosses a threshold, in either direction."""

    def __init__(self) -> None:
        self._levels: dict[str, _SkewLevel] = {}

    def observe(self, venue_name: str, skew_ms: int | None) -> None:
        if skew_ms is None:
            return
        before = self._levels.get(venue_name, _SkewLevel.OK)
        now = _level_of(skew_ms)
        self._levels[venue_name] = now
        if now is before:
            return
        if now is _SkewLevel.BEYOND_LIMIT:
            logger.error(
                "[clock-skew] %s: local clock is %+d ms from the exchange's, at or beyond "
                "the %d ms it tolerates; signed requests will be rejected (-1021) "
                "until the clock is synced",
                venue_name,
                skew_ms,
                FAIL_AT_MS,
            )
        elif now is _SkewLevel.DRIFTING:
            logger.warning(
                "[clock-skew] %s: local clock is %+d ms from the exchange's, above the "
                "%d ms warn line and drifting toward the %d ms limit",
                venue_name,
                skew_ms,
                WARN_ABOVE_MS,
                FAIL_AT_MS,
            )
        else:
            logger.info(
                "[clock-skew] %s: local clock is back within %d ms of the exchange's "
                "(%+d ms) [clock-skew-recovered]",
                venue_name,
                WARN_ABOVE_MS,
                skew_ms,
            )
