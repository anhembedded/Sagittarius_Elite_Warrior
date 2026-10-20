"""The wait a platform asks for, as a `timedelta` that cannot overflow (`EPIC-036C1`).

Discord and Telegram both name a wait in seconds, in the body or in `Retry-After`. The number is
the platform's, so it is not trusted to be small: `timedelta` raises `OverflowError` on a huge one
and `now + wait` on a merely large one, either of which would break the port's rule that a channel
never raises. The wait is capped at `MAX_RETRY_AFTER`, the longest an alert lives
(`DeliveryPolicy.expiry`, decision N2): a wait past it ends in the alert's expiry whatever the
number was, so the cap is never shorter in effect. An infinite number is "longer than anything"
and is capped like a huge one; a value that is NaN or not positive is not a wait.
"""

from __future__ import annotations

import math
from datetime import timedelta

#: Equal to `DeliveryPolicy.expiry`: an alert older than this is never sent.
MAX_RETRY_AFTER = timedelta(hours=24)


def seconds_of(value: float) -> float:
    """`value` as a float; an integer too large for one is infinitely long, not an error."""
    try:
        return float(value)
    except OverflowError:
        return math.inf


def wait_of(seconds: float | None) -> timedelta | None:
    """`seconds` as a wait rounded up to the millisecond and capped; `None` when it is NaN, not
    positive or absent."""
    if seconds is None or math.isnan(seconds) or seconds <= 0:
        return None
    if seconds >= MAX_RETRY_AFTER.total_seconds():
        return MAX_RETRY_AFTER
    # Rounded up to the millisecond: never a hair earlier than the platform asked.
    return timedelta(milliseconds=max(1, math.ceil(seconds * 1000)))
