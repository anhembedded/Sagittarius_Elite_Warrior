"""`EPIC-029C` — Average True Range (Wilder), and the range it suggests (ADR D17).

Pure functions over a sequence of candles, not an `IIndicator`: the Grid
planner asks one question of finished history — how wide is a day? — and never
streams a value per bar, so a stateful class would be machinery with nothing to
hold (ADR D17). `Decimal` throughout, so a suggested price never passes through
a float on its way to an order.

Here rather than at the package root because the boundary guard admits a
module only into this package's mathematics sub-packages
(`boundaries/rules.py`, `_COMPUTATION_SUB_PACKAGES`); a file at the root would
be refused to every module that needs it.

@par True range and Wilder's smoothing
`TR = max(high − low, |high − previous close|, |low − previous close|)`; the
first candle has no previous close, so its TR is `high − low`. The first ATR is
the mean of the first `period` true ranges, and each one after it is
`(ATR × (period − 1) + TR) / period` — Wilder's own definition, which every
charting package calls ATR.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

ATR_DEFAULT_PERIOD = 14


@dataclass(frozen=True, slots=True)
class HighLowClose:
    """The three prices of one candle that volatility reads."""

    high: Decimal
    low: Decimal
    close: Decimal

    def __post_init__(self) -> None:
        if self.low > self.high:
            raise ValueError(f"low {self.low} is above high {self.high}")


@dataclass(frozen=True, slots=True)
class PriceRange:
    """A suggested lower and upper limit."""

    lower: Decimal
    upper: Decimal


class NotEnoughCandlesError(ValueError):
    """Fewer candles than the period needs."""


def true_ranges(candles: Sequence[HighLowClose]) -> tuple[Decimal, ...]:
    """One true range per candle."""
    ranges: list[Decimal] = []
    previous_close: Decimal | None = None
    for candle in candles:
        spread = candle.high - candle.low
        if previous_close is None:
            ranges.append(spread)
        else:
            ranges.append(
                max(
                    spread,
                    abs(candle.high - previous_close),
                    abs(candle.low - previous_close),
                )
            )
        previous_close = candle.close
    return tuple(ranges)


def atr(candles: Sequence[HighLowClose], period: int = ATR_DEFAULT_PERIOD) -> Decimal:
    """Wilder's ATR at the last candle.

    @raise ValueError `period` is not positive.
    @raise NotEnoughCandlesError Fewer than `period` candles.
    """
    if period <= 0:
        raise ValueError(f"ATR period must be positive, got {period}")
    ranges = true_ranges(candles)
    if len(ranges) < period:
        raise NotEnoughCandlesError(
            f"ATR({period}) needs {period} candles, got {len(ranges)}"
        )
    value = sum(ranges[:period], Decimal(0)) / period
    for true_range in ranges[period:]:
        value = (value * (period - 1) + true_range) / period
    return value


def atr_range(
    candles: Sequence[HighLowClose],
    period: int = ATR_DEFAULT_PERIOD,
    multiple: Decimal = Decimal(3),
) -> PriceRange:
    """A range `multiple × ATR` wide, centred on the last close.

    The report sizes a grid's range at 2–4 daily ATRs; `multiple` is the user's
    choice inside (or outside) that band. A suggestion only: the planner never
    writes it into the user's parameters.
    """
    if multiple <= 0:
        raise ValueError(f"multiple must be positive, got {multiple}")
    half_width = atr(candles, period) * multiple / 2
    last_close = candles[-1].close
    return PriceRange(last_close - half_width, last_close + half_width)
