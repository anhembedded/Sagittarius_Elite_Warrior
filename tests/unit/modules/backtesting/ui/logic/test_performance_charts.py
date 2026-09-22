"""Tests for `logic/performance_charts.py` (BOT-106D)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.performance_charts import (
    build_drawdown_chart_points,
    build_yearly_returns_rows,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.theme import (
    BEAR_COLOR,
    BULL_COLOR,
)

_T0 = datetime(2024, 1, 1, tzinfo=UTC)


def _result(equity_curve: list[tuple[datetime, float]]) -> BacktestResult:
    return BacktestResult.compute(
        symbol="ETHUSDT",
        initial_balance=10_000.0,
        final_balance=equity_curve[-1][1] if equity_curve else 10_000.0,
        trades=[],
        equity_curve=equity_curve,
    )


# ---------------------------------------------------------------------------
# build_drawdown_chart_points
# ---------------------------------------------------------------------------


def test_build_drawdown_chart_points_negates_the_percent_for_an_underwater_area():
    equity_curve = [
        (_T0, 10_000.0),
        (_T0 + timedelta(days=1), 9_000.0),
        (_T0 + timedelta(days=2), 10_000.0),
    ]

    points = build_drawdown_chart_points(_result(equity_curve))

    assert points[0]["v"] == 0.0
    assert points[1]["v"] == -10.0
    assert points[2]["v"] == 0.0


def test_build_drawdown_chart_points_uses_epoch_seconds_for_t():
    points = build_drawdown_chart_points(_result([(_T0, 10_000.0)]))

    assert points[0]["t"] == _T0.timestamp()


def test_build_drawdown_chart_points_is_empty_for_an_empty_run():
    assert build_drawdown_chart_points(_result([])) == []


# --- build_yearly_returns_rows -------------------------------------------


def test_build_yearly_returns_rows_is_empty_for_an_empty_run():
    assert build_yearly_returns_rows(_result([])) == []


def test_build_yearly_returns_rows_reports_one_row_per_year_oldest_first():
    equity_curve = [
        (datetime(2023, 1, 15, tzinfo=UTC), 10_000.0),
        (datetime(2023, 6, 15, tzinfo=UTC), 11_000.0),
        (datetime(2024, 3, 15, tzinfo=UTC), 12_100.0),
    ]

    rows = build_yearly_returns_rows(_result(equity_curve))

    assert [row["year"] for row in rows] == [2023, 2024]


def test_build_yearly_returns_rows_leaves_a_month_with_no_data_as_none():
    """`YearlyReturn.months`'s own contract: absent, not zero."""
    equity_curve = [
        (datetime(2024, 1, 15, tzinfo=UTC), 10_000.0),
        (datetime(2024, 3, 15, tzinfo=UTC), 11_000.0),
    ]

    rows = build_yearly_returns_rows(_result(equity_curve))

    months = rows[0]["months"]
    assert months[0] is not None  # January
    assert months[1] is None  # February — never reached
    assert months[2] is not None  # March


def test_build_yearly_returns_rows_colors_a_gain_bull_and_a_loss_bear():
    equity_curve = [
        (datetime(2024, 1, 1, tzinfo=UTC), 10_000.0),
        (datetime(2024, 1, 31, tzinfo=UTC), 11_000.0),
        (datetime(2024, 2, 28, tzinfo=UTC), 9_000.0),
    ]

    rows = build_yearly_returns_rows(_result(equity_curve))

    months = rows[0]["months"]
    assert months[0]["color"] == BULL_COLOR  # January gained
    assert months[1]["color"] == BEAR_COLOR  # February lost
    assert months[0]["text"] == "+10.00%"


def test_build_yearly_returns_rows_reports_the_compounded_ytd_figure():
    equity_curve = [
        (datetime(2024, 1, 1, tzinfo=UTC), 10_000.0),
        (datetime(2024, 1, 31, tzinfo=UTC), 11_000.0),
        (datetime(2024, 2, 28, tzinfo=UTC), 12_100.0),
    ]

    rows = build_yearly_returns_rows(_result(equity_curve))

    # +10% then +10% compounds to +21%, not +20%.
    assert rows[0]["ytdText"] == "+21.00%"
    assert rows[0]["ytdColor"] == BULL_COLOR
