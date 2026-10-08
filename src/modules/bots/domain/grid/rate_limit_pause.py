"""`EPIC-035D` — how a Grid waits out a rate limit the exchange imposed.

A rate limit (HTTP 429, `-1003`, `-1015`) or a ban (HTTP 418) names a pause. The
bot halts for exactly that long, with the reason `RATE_LIMITED`, and resumes by
itself when it ends — the same propose-and-confirm a user's Resume runs. Three
named limits keep that bounded:

  · `AUTO_RESUME_MARGIN` — the wait is the pause plus this, so the first request
    after the pause is not the one the exchange still counts inside it.
  · `MAX_AUTO_RESUME_WAIT` — a pause longer than this (a ban, up to three days) is
    not held by a timer: the bot stays HALTED and says when to resume by hand.
  · `MAX_AUTO_RESUMES` — consecutive automatic resumes that hit the limit again
    before the bot reaches RUNNING. After the last, the bot stays HALTED and says
    so: a limit that never lifts needs a person.
"""

from __future__ import annotations

from datetime import timedelta

AUTO_RESUME_MARGIN = timedelta(seconds=2)
MAX_AUTO_RESUME_WAIT = timedelta(hours=1)
MAX_AUTO_RESUMES = 5


def resume_delay(retry_after: timedelta) -> timedelta | None:
    """When to resume after a pause of `retry_after`, or `None` when a timer is
    not to hold a wait that long."""
    if retry_after > MAX_AUTO_RESUME_WAIT:
        return None
    return retry_after + AUTO_RESUME_MARGIN


def whole_seconds(pause: timedelta) -> int:
    """`pause` in the seconds the exchange would say, rounded up."""
    return int(-(-pause.total_seconds() // 1))
