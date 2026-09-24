"""Tests for `logic/out_of_sample_comparison_rules.py` (`BOT-107A`)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_metrics import (
    BacktestMetrics,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.out_of_sample_validation import (
    OUT_OF_SAMPLE_DIVERGENCE_WARNING_POINTS,
    OutOfSampleValidation,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.out_of_sample_comparison_rules import (
    build_out_of_sample_metric_rows,
    build_overfit_warning,
    build_split_description,
    split_timestamp,
)

_T0 = datetime(2024, 1, 1, tzinfo=UTC)


def _metrics(net_profit_percent: float = 1.0) -> BacktestMetrics:
    return BacktestMetrics(
        net_profit=100.0,
        net_profit_percent=net_profit_percent,
        gross_profit=200.0,
        gross_loss=-100.0,
        max_drawdown_percent=5.0,
        total_closed_trades=10,
        percent_profitable=60.0,
        profit_factor=2.0,
        avg_trade=10.0,
        avg_winning_trade=20.0,
        avg_losing_trade=-10.0,
        largest_winning_trade=50.0,
        largest_losing_trade=-30.0,
        sharpe_ratio=1.5,
        sortino_ratio=2.0,
        max_consecutive_losses=3,
    )


def _result(
    net_profit_percent: float = 1.0,
    equity_curve: list[tuple[datetime, float]] | None = None,
) -> BacktestResult:
    curve = equity_curve if equity_curve is not None else [(_T0, 10_000.0)]
    result = BacktestResult.compute(
        symbol="BTCUSDT",
        initial_balance=10_000.0,
        final_balance=curve[-1][1] if curve else 10_000.0,
        trades=[],
        equity_curve=curve,
    )
    return result.__class__(
        symbol=result.symbol,
        initial_balance=result.initial_balance,
        final_balance=result.final_balance,
        trades=result.trades,
        equity_curve=result.equity_curve,
        metrics=_metrics(net_profit_percent),
    )


def _validation(
    in_sample_net_profit_percent: float,
    out_of_sample_net_profit_percent: float,
    *,
    in_sample_ratio: float = 0.7,
    in_sample_equity_curve: list[tuple[datetime, float]] | None = None,
) -> OutOfSampleValidation:
    return OutOfSampleValidation(
        in_sample=_result(in_sample_net_profit_percent, in_sample_equity_curve),
        out_of_sample=_result(out_of_sample_net_profit_percent),
        in_sample_ratio=in_sample_ratio,
    )


# ---------------------------------------------------------------------------
# build_split_description
# ---------------------------------------------------------------------------


def test_split_description_names_both_shares_from_the_ratio():
    validation = _validation(1.0, 1.0, in_sample_ratio=0.7)

    description = build_split_description(validation)

    assert "70%" in description
    assert "30%" in description


# ---------------------------------------------------------------------------
# build_overfit_warning — reuses BOT-080's own `has_high_divergence`,
# mutation check: a wrong threshold or direction would flip these.
# ---------------------------------------------------------------------------


def test_no_warning_when_out_of_sample_matches_in_sample():
    validation = _validation(10.0, 10.0)

    assert build_overfit_warning(validation) == ""


def test_no_warning_when_out_of_sample_beats_in_sample():
    """BOT-080's own rule only fires when OOS is WORSE, never when it's
    better — mirrored here rather than re-derived."""
    validation = _validation(10.0, 50.0)

    assert build_overfit_warning(validation) == ""


def test_no_warning_exactly_at_the_divergence_threshold():
    """`has_high_divergence` is a strict `>` — exactly at the threshold must
    stay clean, not fire (mutation check: `>=` would flip this)."""
    validation = _validation(OUT_OF_SAMPLE_DIVERGENCE_WARNING_POINTS, 0.0)

    assert build_overfit_warning(validation) == ""


def test_warning_fires_and_names_the_threshold_once_divergence_exceeds_it():
    validation = _validation(50.0, 10.0)

    warning = build_overfit_warning(validation)

    assert warning != ""
    assert f"{OUT_OF_SAMPLE_DIVERGENCE_WARNING_POINTS:.0f}" in warning
    assert "40.0" in warning


# ---------------------------------------------------------------------------
# build_out_of_sample_metric_rows — delegates to
# report_comparison_rules.build_metric_comparison_rows, not a reimplementation
# ---------------------------------------------------------------------------


def test_metric_rows_compare_out_of_sample_against_in_sample():
    validation = _validation(10.0, 5.0)

    rows = build_out_of_sample_metric_rows(validation)

    row = next(r for r in rows if r.label == "Net Profit %")
    assert row.value_a == "10.00%"
    assert row.value_b == "5.00%"


# ---------------------------------------------------------------------------
# split_timestamp
# ---------------------------------------------------------------------------


def test_split_timestamp_is_the_in_samples_last_equity_point():
    last_point_time = _T0 + timedelta(hours=5)
    validation = _validation(
        1.0,
        1.0,
        in_sample_equity_curve=[(_T0, 10_000.0), (last_point_time, 10_100.0)],
    )

    assert split_timestamp(validation) == last_point_time.timestamp()


def test_split_timestamp_is_none_when_in_sample_has_no_equity_points():
    validation = _validation(1.0, 1.0, in_sample_equity_curve=[])

    assert split_timestamp(validation) is None
