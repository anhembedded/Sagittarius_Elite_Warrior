"""`EPIC-026L` — when the cap trips: at the figure, or when it cannot tell for too long."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.loss_cap.loss_cap_policy import (
    UNJUDGED_TRIP_AFTER,
    loss_reached,
    unjudged_too_long,
)

NOW = datetime(2026, 10, 20, 9, 0, tzinfo=UTC)
LIMIT = Decimal(500)


def test_a_loss_one_cent_short_of_the_figure_does_not_trip() -> None:
    assert not loss_reached(Decimal("-499.99"), LIMIT)


def test_a_loss_exactly_at_the_figure_trips() -> None:
    assert loss_reached(Decimal(-500), LIMIT)


def test_a_loss_beyond_the_figure_trips_and_a_gain_never_does() -> None:
    assert loss_reached(Decimal("-500.01"), LIMIT)
    assert not loss_reached(Decimal(900), LIMIT)
    assert not loss_reached(Decimal(0), LIMIT)


def test_not_being_able_to_judge_trips_only_after_the_grace() -> None:
    assert not unjudged_too_long(None, NOW)
    assert not unjudged_too_long(NOW - UNJUDGED_TRIP_AFTER + timedelta(seconds=1), NOW)
    assert unjudged_too_long(NOW - UNJUDGED_TRIP_AFTER, NOW)
