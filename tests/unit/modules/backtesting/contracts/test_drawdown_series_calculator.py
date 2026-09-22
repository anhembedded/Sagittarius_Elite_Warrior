"""`calculate_drawdown_series` (BOT-106C) — the running peak-to-trough curve."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_metrics import (
    BacktestMetrics,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.drawdown_series_calculator import (
    calculate_drawdown_series,
)

_T0 = datetime(2024, 1, 1, tzinfo=UTC)


def _at(hours: int) -> datetime:
    return _T0 + timedelta(hours=hours)


def test_empty_curve_returns_empty_series():
    assert calculate_drawdown_series([]) == []


def test_flat_and_rising_equity_never_draws_down():
    curve = [(_at(0), 1000.0), (_at(1), 1000.0), (_at(2), 1100.0), (_at(3), 1200.0)]

    series = calculate_drawdown_series(curve)

    assert [round(v, 6) for _, v in series] == [0.0, 0.0, 0.0, 0.0]
    assert [t for t, _ in series] == [_at(0), _at(1), _at(2), _at(3)]


def test_drop_from_a_peak_computes_percent_of_that_peak():
    # peak 1000 -> 900: (1000-900)/1000*100 = 10%
    curve = [(_at(0), 1000.0), (_at(1), 900.0)]

    series = calculate_drawdown_series(curve)

    assert series[0][1] == 0.0
    assert series[1][1] == 10.0


def test_recovering_past_the_old_peak_resets_drawdown_to_zero_and_tracks_new_peak():
    curve = [(_at(0), 1000.0), (_at(1), 900.0), (_at(2), 1200.0), (_at(3), 1080.0)]

    series = calculate_drawdown_series(curve)

    assert [round(v, 6) for _, v in series] == [0.0, 10.0, 0.0, 10.0]


def test_max_of_the_series_matches_backtest_metrics_max_drawdown_percent():
    """Both must be the exact same running-peak definition — this is the
    consistency invariant the module's own docstring claims."""
    curve = [
        (_at(0), 1000.0),
        (_at(1), 1200.0),
        (_at(2), 800.0),
        (_at(3), 950.0),
        (_at(4), 1500.0),
        (_at(5), 1000.0),
    ]

    series = calculate_drawdown_series(curve)
    metrics = BacktestMetrics.compute([], curve, initial_balance=1000.0)

    assert max(v for _, v in series) == metrics.max_drawdown_percent
