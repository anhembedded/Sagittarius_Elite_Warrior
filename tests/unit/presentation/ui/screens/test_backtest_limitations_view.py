"""Tests for build_backtest_limitations (BOT-081)."""

from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.domain.backtesting.backtest_metrics import (
    BacktestMetrics,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.out_of_sample_validation import (
    OutOfSampleValidation,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.backtest_limitations_view import (
    build_backtest_limitations,
)

_T0 = datetime(2026, 1, 1, tzinfo=UTC)


def _result(out_of_sample: OutOfSampleValidation | None = None) -> BacktestResult:
    return BacktestResult(
        symbol="ETHUSDT",
        initial_balance=1000.0,
        final_balance=1000.0,
        trades=[],
        equity_curve=[],
        metrics=BacktestMetrics.compute([], [], 1000.0),
        out_of_sample=out_of_sample,
    )


def test_always_applicable_limitations_are_present_for_every_run():
    limitations = build_backtest_limitations(_result())

    joined = " ".join(limitations)
    assert "slippage" in joined
    assert "độ trễ mạng" in joined
    assert "sổ lệnh" in joined
    assert "Stop Loss" in joined
    assert "giá mở nến kế tiếp" in joined
    assert "Phí giao dịch" in joined
    assert "Static" in joined


def test_out_of_sample_note_appears_when_the_run_has_no_split():
    limitations = build_backtest_limitations(_result(out_of_sample=None))

    assert any("out-of-sample" in note for note in limitations)


def test_out_of_sample_note_is_absent_when_the_run_has_a_real_split():
    metrics = BacktestMetrics.compute([], [], 1000.0)
    healthy_result = BacktestResult(
        symbol="ETHUSDT",
        initial_balance=1000.0,
        final_balance=1000.0,
        trades=[],
        equity_curve=[],
        metrics=metrics,
    )
    validation = OutOfSampleValidation(
        in_sample=healthy_result,
        out_of_sample=healthy_result,
        in_sample_ratio=0.7,
    )

    limitations = build_backtest_limitations(_result(out_of_sample=validation))

    assert not any("out-of-sample" in note for note in limitations)
