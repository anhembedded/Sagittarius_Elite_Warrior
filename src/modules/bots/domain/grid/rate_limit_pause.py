"""`EPIC-035D`, `EPIC-042F` — how a Grid waits out a rate limit the exchange imposed.

A rate limit (HTTP 429, `-1003`, `-1015`) or a ban (HTTP 418) names a pause. The bot waits for
exactly that long, with the reason `RATE_LIMITED`, and resumes by itself when it ends: since
`EPIC-042F` that is the halt-recovery mechanism (`halt_recovery_policy.py`), whose rule for the
reason is the Grid's kind layer (`grid_kind.py` → `GRID_RECOVERY_LAYER`) and whose probe is
*the pause has ended* (`GridRateLimitPause.holds`). Two named limits stay here:

  · `AUTO_RESUME_MARGIN` — the pause plus this is when the first request is safe, so it is not
    the one the exchange still counts inside the pause. The recovery rule's dwell is this value:
    the pause must be over, continuously, for the margin before the attempt. A stop that waits
    out a pause retries after the same margin (`GridStopRetry`).
  · `MAX_AUTO_RESUME_WAIT` — a pause longer than this (a ban, up to three days) is not waited
    for: the bot halts for a person and says when to resume by hand.

The consecutive counter that used to bound the resumes (`MAX_AUTO_RESUMES`) is retired: the
rolling budget of the bot's recovery ledger bounds every automatic recovery, this one included.
"""

from __future__ import annotations

from datetime import timedelta

from Sagittarius_Elite_Warrior.src.modules.bots.domain.halt_recovery_policy import (
    PAUSE_DWELL,
)

AUTO_RESUME_MARGIN = PAUSE_DWELL
MAX_AUTO_RESUME_WAIT = timedelta(hours=1)


def too_long_to_wait_words(retry_after: timedelta | None) -> str:
    """What a halt says when the pause is longer than `MAX_AUTO_RESUME_WAIT`, or the empty string
    when it is a pause the bot waits for (`retry_after` is `None` when the exchange named none)."""
    if retry_after is None or retry_after <= MAX_AUTO_RESUME_WAIT:
        return ""
    return (
        f"the pause is longer than {whole_seconds(MAX_AUTO_RESUME_WAIT)} s, "
        "which no automatic resume waits for; resume by hand once it ends"
    )


def whole_seconds(pause: timedelta) -> int:
    """`pause` in the seconds the exchange would say, rounded up."""
    return int(-(-pause.total_seconds() // 1))
