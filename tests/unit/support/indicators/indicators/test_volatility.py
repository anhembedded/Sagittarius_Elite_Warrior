"""`EPIC-029C` — Wilder's ATR and the range it suggests.

Known answers worked by hand, each from a case whose result does not depend on
re-typing the formula: a constant true range has that range as its ATR under any
smoothing, a gap is the case true range exists for, and four candles with
period 3 are small enough to follow Wilder's recurrence on paper.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.support.indicators.indicators.volatility import (
    HighLowClose,
    NotEnoughCandlesError,
    atr,
    atr_range,
    true_ranges,
)


def _c(high: str, low: str, close: str) -> HighLowClose:
    return HighLowClose(Decimal(high), Decimal(low), Decimal(close))


def test_the_first_true_range_is_the_spread() -> None:
    assert true_ranges([_c("10", "8", "9")]) == (Decimal(2),)


def test_a_gap_up_widens_the_true_range_to_the_previous_close() -> None:
    """Spread 1, but the high is 3 above the previous close of 9."""
    assert true_ranges([_c("10", "8", "9"), _c("12", "11", "11.5")])[1] == Decimal(3)


def test_a_gap_down_widens_the_true_range_to_the_previous_close() -> None:
    assert true_ranges([_c("10", "8", "9"), _c("7", "6", "6.5")])[1] == Decimal(3)


def test_a_constant_true_range_is_its_own_atr() -> None:
    candles = [_c("12", "10", "11")] * 30
    assert atr(candles, 14) == Decimal(2)


def test_wilder_recurrence_by_hand() -> None:
    """True ranges 2, 4, 6, 8 at period 3: seed (2+4+6)/3 = 4, then (4×2+8)/3 = 16/3."""
    candles = [
        _c("11", "9", "10"),
        _c("12", "8", "10"),
        _c("13", "7", "10"),
        _c("14", "6", "10"),
    ]
    assert true_ranges(candles) == (Decimal(2), Decimal(4), Decimal(6), Decimal(8))
    assert atr(candles[:3], 3) == Decimal(4)
    assert atr(candles, 3) == Decimal(16) / Decimal(3)


def test_atr_needs_period_candles() -> None:
    with pytest.raises(NotEnoughCandlesError):
        atr([_c("11", "9", "10")] * 13, 14)
    with pytest.raises(ValueError, match="positive"):
        atr([_c("11", "9", "10")], 0)


def test_atr_range_is_multiple_atrs_wide_centred_on_the_last_close() -> None:
    candles = [_c("12", "10", "11")] * 20
    suggestion = atr_range(candles, period=14, multiple=Decimal(3))
    assert suggestion.lower == Decimal(8)
    assert suggestion.upper == Decimal(14)


def test_a_candle_with_low_above_high_is_refused() -> None:
    with pytest.raises(ValueError, match="above high"):
        _c("9", "10", "9")


def test_a_candle_with_low_equal_to_high_is_allowed() -> None:
    assert true_ranges([_c("10", "10", "10")]) == (Decimal(0),)


def test_atr_range_needs_a_positive_multiple() -> None:
    with pytest.raises(ValueError, match="positive"):
        atr_range([_c("12", "10", "11")] * 20, multiple=Decimal(0))
