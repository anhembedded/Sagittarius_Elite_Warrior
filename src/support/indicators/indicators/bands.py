"""`EPIC-029C` — Bollinger Bands at the last candle (ADR D17).

A pure function over closes, for the same reason `volatility.py` is (one
question of finished history, never a streamed value). `middle` is the simple
mean of the last `period` closes; the bands are `middle ± deviations × σ`,
where σ is the **population** standard deviation of those closes — Bollinger's
own definition, and what charting packages draw.

`Decimal.sqrt()` keeps the result exact to the context's precision instead of
passing through a float.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.support.indicators.indicators.volatility import (
    NotEnoughCandlesError,
)

BOLLINGER_DEFAULT_PERIOD = 20
BOLLINGER_DEFAULT_DEVIATIONS = Decimal(2)


@dataclass(frozen=True, slots=True)
class BollingerBands:
    """The three lines at the last candle."""

    lower: Decimal
    middle: Decimal
    upper: Decimal


def bollinger(
    closes: Sequence[Decimal],
    period: int = BOLLINGER_DEFAULT_PERIOD,
    deviations: Decimal = BOLLINGER_DEFAULT_DEVIATIONS,
) -> BollingerBands:
    """The bands over the last `period` closes.

    @raise ValueError `period` is not positive or `deviations` is negative.
    @raise NotEnoughCandlesError Fewer than `period` closes.
    """
    if period <= 0:
        raise ValueError(f"Bollinger period must be positive, got {period}")
    if deviations < 0:
        raise ValueError(f"deviations must not be negative, got {deviations}")
    if len(closes) < period:
        raise NotEnoughCandlesError(
            f"Bollinger({period}) needs {period} closes, got {len(closes)}"
        )
    window = closes[-period:]
    middle = sum(window, Decimal(0)) / period
    variance = sum(((close - middle) ** 2 for close in window), Decimal(0)) / period
    width = deviations * variance.sqrt()
    return BollingerBands(middle - width, middle, middle + width)
