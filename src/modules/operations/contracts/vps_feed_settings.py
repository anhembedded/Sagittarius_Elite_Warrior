"""`EPIC-047H` — the three settings of what the host reads and writes for the VPS tab, judged once.

@details Both numbers are host settings, not constants (decision record 2026-10-27, D4), and the
bounds are enforced here, in code: a typo cannot raise the ceiling to the soft line the exit
reserve starts at (70 % of the minute's weight), nor refresh a bot every second. A value outside
its bounds is raised or lowered to the nearest bound and the setting says so (`notes`), so the
host logs it once; nothing here raises, because a host that will not start for a typo in a setting
about a view is worse than a view that is slower.

@par Extension cases
  · a per-venue ceiling - the field becomes a mapping and `judged` clamps each value;
  · a different cadence for fills - one more field beside `fills_every_rounds`.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Seconds between two refreshes of one bot's exchange facts (decision record D4).
REFRESH_INTERVAL_DEFAULT_S = 120
#: The fastest a bot may be refreshed; a lower setting is raised to this. 0 is off, not "fastest".
REFRESH_INTERVAL_LOWEST_S = 30
#: Percent of the venue's per-minute weight all of the host's reads for the tab may spend.
CEILING_DEFAULT_PCT = 3.0
#: The highest ceiling a setting may reach: well under the 70 % soft line (`ExchangeCallPolicy`).
CEILING_HIGHEST_PCT = 10.0
#: A bot's fills are read again every this many rounds (and on demand): an account-history read is
#: 20 weight per day window (`i_account_history_reader.py`), far dearer than the other reads.
FILLS_EVERY_ROUNDS = 5


@dataclass(frozen=True, slots=True)
class VpsFeedSettings:
    #: Seconds between refreshes of one bot; 0 turns the refresh off.
    refresh_interval_s: int
    ceiling_pct: float
    market_recorder_enabled: bool
    #: What `judged` changed, in words for the log; empty when every value was as given.
    notes: tuple[str, ...] = ()
    fills_every_rounds: int = FILLS_EVERY_ROUNDS
    #: Whether this process runs the feed at all; off in the GUI entry point (`EPIC-047H`).
    feed_enabled: bool = True

    @property
    def refresh_enabled(self) -> bool:
        return self.refresh_interval_s > 0

    @staticmethod
    def judged(
        refresh_interval_s: float, ceiling_pct: float, market_recorder_enabled: bool
    ) -> VpsFeedSettings:
        notes: list[str] = []
        interval = int(refresh_interval_s)
        if interval < 0:
            notes.append(
                f"refresh interval {interval} s is negative; using {REFRESH_INTERVAL_DEFAULT_S} s"
            )
            interval = REFRESH_INTERVAL_DEFAULT_S
        elif 0 < interval < REFRESH_INTERVAL_LOWEST_S:
            notes.append(
                f"refresh interval {interval} s is below {REFRESH_INTERVAL_LOWEST_S} s; using that"
            )
            interval = REFRESH_INTERVAL_LOWEST_S
        ceiling = float(ceiling_pct)
        if ceiling <= 0:
            notes.append(
                f"weight ceiling {ceiling:g} % is not positive; using {CEILING_DEFAULT_PCT:g} %"
            )
            ceiling = CEILING_DEFAULT_PCT
        elif ceiling > CEILING_HIGHEST_PCT:
            notes.append(
                f"weight ceiling {ceiling:g} % is above {CEILING_HIGHEST_PCT:g} %; using that"
            )
            ceiling = CEILING_HIGHEST_PCT
        return VpsFeedSettings(interval, ceiling, market_recorder_enabled, tuple(notes))
