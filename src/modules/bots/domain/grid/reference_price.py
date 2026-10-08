"""`EPIC-035J` — how old the price a Grid acts on may be, and how far it may move.

A tick is heard about every two seconds while a pair trades, yet a Grid can sit
HALTED or PAUSED for hours and then use "the last tick" for a resume proposal,
a stop's slices or its dust check. Two limits make the price an input with an
age rather than a remembered number:

  · `REFERENCE_PRICE_MAX_AGE_SECONDS` — a price older than this is not used; the
    book is read instead. Five missed pushes of the stream, so a healthy feed
    never triggers a read and a quiet one always does.
  · `RESUME_PRICE_TOLERANCE` — a resume ladder is proposed at one price and laid
    at the user's confirmation, perhaps minutes later. If the market has moved
    by more than this fraction of the proposed price the ladder is refused, not
    laid: its sides and quantities were decided for a price the market left. A
    fresh resume proposes again.
"""

from __future__ import annotations

from decimal import Decimal

REFERENCE_PRICE_MAX_AGE_SECONDS: float = 10.0
RESUME_PRICE_TOLERANCE: Decimal = Decimal("0.01")


def price_is_too_old(heard_at: float, now: float, limit: float) -> bool:
    """Whether a price heard at `heard_at` is `limit` seconds old at `now`.

    The boundary is too old, as for `price_is_stale`.

    @raise ValueError `limit` is not positive."""
    if limit <= 0:
        raise ValueError(f"the age limit must be positive, got {limit}")
    return now - heard_at >= limit


def moved_beyond(proposed: Decimal, current: Decimal, tolerance: Decimal) -> bool:
    """Whether `current` differs from `proposed` by more than `tolerance` of
    `proposed`. Exactly at the tolerance is still inside.

    @raise ValueError `proposed` is not positive, or `tolerance` is negative."""
    if proposed <= 0:
        raise ValueError(f"the proposed price must be positive, got {proposed}")
    if tolerance < 0:
        raise ValueError(f"the tolerance must not be negative, got {tolerance}")
    return abs(current - proposed) > proposed * tolerance
