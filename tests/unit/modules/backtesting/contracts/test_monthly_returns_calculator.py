"""`calculate_monthly_returns`/`calculate_yearly_returns` (BOT-106C)."""

from __future__ import annotations

import math
from datetime import UTC, datetime

import pytest
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.monthly_returns_calculator import (
    MonthlyReturn,
    calculate_monthly_returns,
    calculate_yearly_returns,
)


def _t(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, tzinfo=UTC)


def test_empty_curve_returns_no_months():
    assert calculate_monthly_returns([], initial_balance=1000.0) == []


def test_single_month_measures_from_initial_balance():
    curve = [(_t(2026, 1, 5), 1050.0), (_t(2026, 1, 20), 1100.0)]

    result = calculate_monthly_returns(curve, initial_balance=1000.0)

    assert result == [MonthlyReturn(year=2026, month=1, return_percent=10.0)]


def test_second_month_measures_from_the_first_months_last_point_not_its_first():
    # Jan: 1000 -> 1100 (+10%). Feb: carried in at 1100 -> 1210 (+10% again).
    curve = [
        (_t(2026, 1, 5), 1050.0),
        (_t(2026, 1, 25), 1100.0),
        (_t(2026, 2, 3), 1150.0),
        (_t(2026, 2, 20), 1210.0),
    ]

    result = calculate_monthly_returns(curve, initial_balance=1000.0)

    assert result == [
        MonthlyReturn(year=2026, month=1, return_percent=10.0),
        MonthlyReturn(year=2026, month=2, return_percent=pytest.approx(10.0)),
    ]


def test_a_losing_month_produces_a_negative_return():
    curve = [(_t(2026, 3, 1), 900.0)]

    result = calculate_monthly_returns(curve, initial_balance=1000.0)

    assert result == [MonthlyReturn(year=2026, month=3, return_percent=-10.0)]


def test_year_boundary_is_a_separate_month_entry():
    curve = [(_t(2026, 12, 15), 1100.0), (_t(2027, 1, 10), 1210.0)]

    result = calculate_monthly_returns(curve, initial_balance=1000.0)

    assert [(m.year, m.month) for m in result] == [(2026, 12), (2027, 1)]


def test_yearly_returns_compounds_the_recorded_months_not_a_simple_sum():
    # +10% then +10% compounds to +21%, not +20%.
    monthly = [
        MonthlyReturn(year=2026, month=1, return_percent=10.0),
        MonthlyReturn(year=2026, month=2, return_percent=10.0),
    ]

    result = calculate_yearly_returns(monthly)

    assert len(result) == 1
    assert result[0].year == 2026
    assert result[0].months == {1: 10.0, 2: 10.0}
    assert math.isclose(result[0].ytd_return_percent, 21.0, rel_tol=1e-9)


def test_yearly_returns_ytd_reflects_only_months_seen_so_far():
    monthly = [MonthlyReturn(year=2026, month=1, return_percent=5.0)]

    result = calculate_yearly_returns(monthly)

    assert result[0].ytd_return_percent == pytest.approx(5.0)


def test_yearly_returns_separates_years_and_sorts_them():
    monthly = [
        MonthlyReturn(year=2027, month=1, return_percent=5.0),
        MonthlyReturn(year=2026, month=12, return_percent=-5.0),
    ]

    result = calculate_yearly_returns(monthly)

    assert [y.year for y in result] == [2026, 2027]
    assert result[0].months == {12: -5.0}
    assert result[1].months == {1: 5.0}


def test_a_month_never_reached_is_absent_not_zero():
    monthly = [MonthlyReturn(year=2026, month=3, return_percent=1.0)]

    result = calculate_yearly_returns(monthly)

    assert 1 not in result[0].months
    assert 3 in result[0].months
