"""`EPIC-035A` — the pure rule behind the price-feed staleness HALT.

A feed that goes quiet looks the same as a flat market unless the age of the
last tick is compared with a limit. The rule is on a monotonic clock's seconds,
so a wall-clock step (NTP, a sleep, a manual change) can neither fire it nor
hide it.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.price_freshness import (
    PRICE_STALE_AFTER_SECONDS,
    PRICE_START_GRACE_SECONDS,
    price_is_stale,
)


def test_a_tick_younger_than_the_limit_is_fresh() -> None:
    assert price_is_stale(100.0, 159.9, 60.0) is False


def test_a_tick_exactly_as_old_as_the_limit_is_stale() -> None:
    """The boundary belongs to the safe side: "no tick for N seconds" is N."""
    assert price_is_stale(100.0, 160.0, 60.0) is True


def test_a_tick_older_than_the_limit_is_stale() -> None:
    assert price_is_stale(100.0, 400.0, 60.0) is True


def test_a_clock_that_reads_earlier_than_the_tick_is_never_stale() -> None:
    assert price_is_stale(100.0, 90.0, 60.0) is False


@pytest.mark.parametrize("limit", [0.0, -1.0])
def test_a_limit_that_cannot_be_met_is_refused(limit: float) -> None:
    with pytest.raises(ValueError, match="limit"):
        price_is_stale(100.0, 101.0, limit)


def test_the_named_limits_are_tens_of_seconds_and_bounded() -> None:
    """Binance pushes a kline update about every two seconds while the pair
    trades; tens of seconds is many missed pushes, not a quiet minute."""
    assert 10.0 <= PRICE_STALE_AFTER_SECONDS <= 120.0
    assert 10.0 <= PRICE_START_GRACE_SECONDS <= 120.0
