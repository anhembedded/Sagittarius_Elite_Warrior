"""Tests for `logic/report_comparison_rules.py` (`BOT-115D`)."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_metrics import (
    BacktestMetrics,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.backtest_fsm_matrix import (
    BacktestRunConfig,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.report_comparison_rules import (
    IDENTICAL_CONFIG_TEXT,
    build_config_diff_text,
    build_equity_comparison_series,
    build_loaded_file_label,
    build_market_mismatch_warning,
    build_metric_comparison_rows,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import Tone

_T0 = datetime(2024, 1, 1, tzinfo=UTC)


def _run_config(**overrides) -> BacktestRunConfig:
    defaults = {
        "strategy_key": "ema_crossover",
        "timeframe": TimeFrame.FIVE_MINUTES,
        "initial_balance": 10_000.0,
        "start_time": _T0 - timedelta(days=30),
        "end_time": _T0,
        "symbol": "BTCUSDT",
    }
    defaults.update(overrides)
    return BacktestRunConfig(**defaults)


def _metrics(**overrides) -> BacktestMetrics:
    defaults: dict[str, object] = {
        "net_profit": 100.0,
        "net_profit_percent": 1.0,
        "gross_profit": 200.0,
        "gross_loss": -100.0,
        "max_drawdown_percent": 5.0,
        "total_closed_trades": 10,
        "percent_profitable": 60.0,
        "profit_factor": 2.0,
        "avg_trade": 10.0,
        "avg_winning_trade": 20.0,
        "avg_losing_trade": -10.0,
        "largest_winning_trade": 50.0,
        "largest_losing_trade": -30.0,
        "sharpe_ratio": 1.5,
        "sortino_ratio": 2.0,
        "max_consecutive_losses": 3,
    }
    defaults.update(overrides)
    return BacktestMetrics(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# build_config_diff_text
# ---------------------------------------------------------------------------


def test_identical_configs_report_the_friendly_identical_message():
    config = _run_config()

    assert build_config_diff_text(config, config) == IDENTICAL_CONFIG_TEXT


def test_differing_configs_reuse_compute_diff_summary_verbatim():
    config_a = _run_config(symbol="BTCUSDT")
    config_b = _run_config(symbol="ETHUSDT")

    text = build_config_diff_text(config_a, config_b)

    assert text == config_a.compute_diff_summary(config_b)
    assert "BTCUSDT" in text
    assert "ETHUSDT" in text


# ---------------------------------------------------------------------------
# build_market_mismatch_warning
# ---------------------------------------------------------------------------


def test_same_symbol_and_timeframe_has_no_warning():
    config = _run_config()

    assert build_market_mismatch_warning(config, config) == ""


def test_different_symbol_names_both_markets_in_the_warning():
    config_a = _run_config(symbol="BTCUSDT")
    config_b = _run_config(symbol="ETHUSDT")

    warning = build_market_mismatch_warning(config_a, config_b)

    assert "BTCUSDT" in warning
    assert "ETHUSDT" in warning


def test_different_timeframe_names_both_timeframes_in_the_warning():
    config_a = _run_config(timeframe=TimeFrame.ONE_MINUTE)
    config_b = _run_config(timeframe=TimeFrame.FIVE_MINUTES)

    warning = build_market_mismatch_warning(config_a, config_b)

    assert TimeFrame.ONE_MINUTE.value in warning
    assert TimeFrame.FIVE_MINUTES.value in warning


# ---------------------------------------------------------------------------
# build_metric_comparison_rows — tone direction
# ---------------------------------------------------------------------------


def test_higher_is_better_field_tones_positive_when_b_is_bigger():
    rows = build_metric_comparison_rows(
        _metrics(net_profit=100.0), _metrics(net_profit=200.0)
    )

    row = next(r for r in rows if r.label == "Net Profit")
    assert row.tone is Tone.POSITIVE
    assert row.delta.startswith("+")


def test_higher_is_better_field_tones_negative_when_b_is_smaller():
    rows = build_metric_comparison_rows(
        _metrics(net_profit=200.0), _metrics(net_profit=100.0)
    )

    row = next(r for r in rows if r.label == "Net Profit")
    assert row.tone is Tone.NEGATIVE


def test_lower_is_better_field_tones_positive_when_b_is_smaller():
    """`max_drawdown_percent` is `_LOWER_IS_BETTER` — mutation check: if the
    row-tone logic used the raw sign instead of consulting that set, this
    would flip to NEGATIVE (a smaller drawdown reads as worse)."""
    rows = build_metric_comparison_rows(
        _metrics(max_drawdown_percent=10.0), _metrics(max_drawdown_percent=4.0)
    )

    row = next(r for r in rows if r.label == "Max Drawdown")
    assert row.tone is Tone.POSITIVE


def test_lower_is_better_field_tones_negative_when_b_is_bigger():
    rows = build_metric_comparison_rows(
        _metrics(max_drawdown_percent=4.0), _metrics(max_drawdown_percent=10.0)
    )

    row = next(r for r in rows if r.label == "Max Drawdown")
    assert row.tone is Tone.NEGATIVE


def test_neutral_field_never_tones_regardless_of_direction():
    rows = build_metric_comparison_rows(
        _metrics(total_closed_trades=5), _metrics(total_closed_trades=50)
    )

    row = next(r for r in rows if r.label == "Total Closed Trades")
    assert row.tone is Tone.NEUTRAL


def test_equal_values_tone_neutral():
    metrics = _metrics()
    rows = build_metric_comparison_rows(metrics, metrics)

    row = next(r for r in rows if r.label == "Net Profit")
    assert row.tone is Tone.NEUTRAL
    assert row.delta == "0"


# ---------------------------------------------------------------------------
# build_equity_comparison_series
# ---------------------------------------------------------------------------


def test_equity_curves_are_rebased_to_percent_of_their_own_starting_balance():
    curve_a = [(_T0, 10_000.0), (_T0 + timedelta(hours=1), 11_000.0)]
    curve_b = [(_T0, 5_000.0), (_T0 + timedelta(hours=1), 5_500.0)]

    points_a, points_b = build_equity_comparison_series(
        curve_a, 10_000.0, curve_b, 5_000.0
    )

    assert math.isclose(points_a[0]["v"], 100.0)
    assert math.isclose(points_a[1]["v"], 110.0)
    assert math.isclose(points_b[0]["v"], 100.0)
    assert math.isclose(points_b[1]["v"], 110.0)


def test_empty_curve_produces_no_points():
    points_a, points_b = build_equity_comparison_series([], 10_000.0, [], 5_000.0)

    assert points_a == []
    assert points_b == []


def test_non_positive_initial_balance_produces_no_points_rather_than_dividing_by_zero():
    curve = [(_T0, 0.0), (_T0 + timedelta(hours=1), 100.0)]

    points, _ = build_equity_comparison_series(curve, 0.0, [], 1.0)

    assert points == []


# ---------------------------------------------------------------------------
# build_loaded_file_label
# ---------------------------------------------------------------------------


def test_loaded_file_label_names_the_basename_not_the_full_path():
    label = build_loaded_file_label("/some/nested/dir/run.sagi-report.json")

    assert label == "run.sagi-report.json"
    assert "/" not in label
