"""Tests for OutOfSampleValidation.has_high_divergence (BOT-080)."""

from Sagittarius_Elite_Warrior.src.domain.backtesting.backtest_metrics import (
    BacktestMetrics,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.out_of_sample_validation import (
    OutOfSampleValidation,
)


def _result_with_net_profit_percent(percent: float) -> BacktestResult:
    metrics = BacktestMetrics(
        net_profit=0.0,
        net_profit_percent=percent,
        gross_profit=0.0,
        gross_loss=0.0,
        max_drawdown_percent=0.0,
        total_closed_trades=0,
        percent_profitable=0.0,
        profit_factor=0.0,
        avg_trade=0.0,
        avg_winning_trade=0.0,
        avg_losing_trade=0.0,
        largest_winning_trade=0.0,
        largest_losing_trade=0.0,
    )
    return BacktestResult(
        symbol="BTCUSDT",
        initial_balance=1000.0,
        final_balance=1000.0,
        trades=[],
        equity_curve=[],
        metrics=metrics,
    )


def test_has_high_divergence_when_in_sample_beats_out_of_sample_by_a_lot():
    # The real overfitting signature: great on tuning data, bad on unseen data.
    validation = OutOfSampleValidation(
        in_sample=_result_with_net_profit_percent(50.0),
        out_of_sample=_result_with_net_profit_percent(-20.0),
        in_sample_ratio=0.7,
    )

    assert validation.has_high_divergence is True


def test_no_divergence_flag_when_results_are_close():
    validation = OutOfSampleValidation(
        in_sample=_result_with_net_profit_percent(10.0),
        out_of_sample=_result_with_net_profit_percent(8.0),
        in_sample_ratio=0.7,
    )

    assert validation.has_high_divergence is False


def test_no_divergence_flag_when_out_of_sample_does_better_than_in_sample():
    """Only the "looked great on tuning data, fell apart on unseen data"
    direction is a red flag — the reverse isn't overfitting."""
    validation = OutOfSampleValidation(
        in_sample=_result_with_net_profit_percent(5.0),
        out_of_sample=_result_with_net_profit_percent(60.0),
        in_sample_ratio=0.7,
    )

    assert validation.has_high_divergence is False
