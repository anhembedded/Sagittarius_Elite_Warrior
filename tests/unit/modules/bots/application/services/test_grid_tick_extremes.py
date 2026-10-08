"""`BUG-191` — `GridTickExtremes` lets a bot act only on the extremes it observed."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_tick_extremes import (
    GridTickExtremes,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_price_tick import (
    PriceTick,
)

_BAR = datetime(2026, 10, 8, 9, tzinfo=UTC)
_NEXT = _BAR + timedelta(minutes=1)


def _tick(last: int, low: int, high: int, bar: datetime | None = _BAR) -> PriceTick:
    return PriceTick(Decimal(last), Decimal(low), Decimal(high), bar)


def test_the_first_update_of_a_run_counts_by_its_close_only() -> None:
    extremes = GridTickExtremes()

    assert extremes.observed(_tick(100, 80, 120)) == (100, 100)


def test_a_new_low_or_high_in_the_same_bar_counts_and_a_repeated_one_does_not() -> None:
    extremes = GridTickExtremes()
    extremes.observed(_tick(100, 80, 120))

    assert extremes.observed(_tick(101, 80, 120)) == (101, 101)
    assert extremes.observed(_tick(101, 79, 121)) == (79, 121)
    assert extremes.observed(_tick(102, 79, 121)) == (102, 102)


def test_a_later_bar_counts_whole_and_an_older_bar_by_its_close() -> None:
    extremes = GridTickExtremes()
    extremes.observed(_tick(100, 80, 120))

    assert extremes.observed(_tick(100, 85, 105, _NEXT)) == (85, 105)
    assert extremes.observed(_tick(100, 70, 130, _BAR)) == (100, 100)


def test_a_reset_starts_the_next_run_with_a_first_update_again() -> None:
    extremes = GridTickExtremes()
    extremes.observed(_tick(100, 100, 100))
    extremes.reset()

    assert extremes.observed(_tick(100, 80, 120)) == (100, 100)


def test_a_lone_price_has_no_range_beyond_itself() -> None:
    assert GridTickExtremes().observed(PriceTick.at(Decimal(95))) == (95, 95)
