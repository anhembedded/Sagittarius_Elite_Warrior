"""`EPIC-029C` — Bollinger Bands, against closed-form answers.

The closes 1, 2, …, 20 have mean 10.5 and population variance (20² − 1) / 12 =
33.25, a closed form independent of the implementation; a constant series has
zero width.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.support.indicators.indicators.bands import (
    bollinger,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicators.volatility import (
    NotEnoughCandlesError,
)


def test_one_to_twenty() -> None:
    bands = bollinger([Decimal(n) for n in range(1, 21)])
    sigma = Decimal("33.25").sqrt()
    assert bands.middle == Decimal("10.5")
    assert bands.upper == Decimal("10.5") + 2 * sigma
    assert bands.lower == Decimal("10.5") - 2 * sigma
    assert sigma.quantize(Decimal("0.000001")) == Decimal("5.766281")


def test_only_the_last_period_closes_count() -> None:
    closes = [Decimal(1000)] * 5 + [Decimal(n) for n in range(1, 21)]
    assert bollinger(closes).middle == Decimal("10.5")


def test_a_constant_series_has_zero_width() -> None:
    bands = bollinger([Decimal(7)] * 20)
    assert bands.lower == bands.middle == bands.upper == Decimal(7)


def test_deviations_scale_the_width() -> None:
    closes = [Decimal(n) for n in range(1, 21)]
    one = bollinger(closes, deviations=Decimal(1))
    three = bollinger(closes, deviations=Decimal(3))
    assert three.upper - three.middle == 3 * (one.upper - one.middle)


def test_invalid_inputs() -> None:
    with pytest.raises(NotEnoughCandlesError):
        bollinger([Decimal(1)] * 19)
    with pytest.raises(ValueError, match="positive"):
        bollinger([Decimal(1)] * 20, period=0)
    with pytest.raises(ValueError, match="negative"):
        bollinger([Decimal(1)] * 20, deviations=Decimal(-1))


def test_zero_deviations_collapse_the_bands_onto_the_middle() -> None:
    bands = bollinger([Decimal(n) for n in range(1, 21)], deviations=Decimal(0))
    assert bands.lower == bands.middle == bands.upper == Decimal("10.5")
