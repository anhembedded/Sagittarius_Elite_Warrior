"""`EPIC-035J` — the age limit and the move tolerance, at their boundaries."""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.reference_price import (
    REFERENCE_PRICE_MAX_AGE_SECONDS,
    RESUME_PRICE_TOLERANCE,
    moved_beyond,
    price_is_too_old,
)


def test_a_price_is_too_old_exactly_at_the_limit() -> None:
    limit = REFERENCE_PRICE_MAX_AGE_SECONDS
    assert not price_is_too_old(100.0, 100.0 + limit - 0.001, limit)
    assert price_is_too_old(100.0, 100.0 + limit, limit)


@pytest.mark.parametrize("limit", [0.0, -1.0])
def test_a_limit_that_cannot_be_met_is_refused(limit: float) -> None:
    with pytest.raises(ValueError, match="positive"):
        price_is_too_old(0.0, 1.0, limit)


def test_a_move_of_exactly_the_tolerance_is_still_inside() -> None:
    proposed = Decimal(200)
    edge = proposed * RESUME_PRICE_TOLERANCE
    assert not moved_beyond(proposed, proposed + edge, RESUME_PRICE_TOLERANCE)
    assert not moved_beyond(proposed, proposed - edge, RESUME_PRICE_TOLERANCE)
    assert moved_beyond(
        proposed, proposed + edge + Decimal("0.01"), RESUME_PRICE_TOLERANCE
    )
    assert moved_beyond(
        proposed, proposed - edge - Decimal("0.01"), RESUME_PRICE_TOLERANCE
    )


def test_a_move_is_judged_against_the_proposed_price() -> None:
    assert moved_beyond(Decimal(100), Decimal(102), Decimal("0.01"))
    assert not moved_beyond(Decimal(1000), Decimal(1002), Decimal("0.01"))


@pytest.mark.parametrize(
    ("proposed", "tolerance"),
    [(Decimal(0), Decimal("0.01")), (Decimal(1), Decimal(-1))],
)
def test_a_meaningless_comparison_is_refused(
    proposed: Decimal, tolerance: Decimal
) -> None:
    with pytest.raises(ValueError):
        moved_beyond(proposed, Decimal(1), tolerance)
