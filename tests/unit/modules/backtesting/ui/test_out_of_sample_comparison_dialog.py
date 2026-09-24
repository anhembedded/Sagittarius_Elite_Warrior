"""`OutOfSampleComparisonDialog` against a real `BackTestViewModel` (`BOT-107A`).

What only a test building the real composition root can prove: that the
dialog really reads `run_result.comparison_snapshot().result.out_of_sample`,
and that a `statCardsChanged` emission (the same signal the Presenter fires
alongside `set_comparison_snapshot`) refreshes an already-open dialog.

The comparison math itself — split description, overfit warning, metric
tone — is `logic/test_out_of_sample_comparison_rules.py`'s, with no dialog
in sight.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import UTC, datetime, timedelta

from PySide6.QtWidgets import QPushButton
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.out_of_sample_validation import (
    OutOfSampleValidation,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.trade import Trade
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_modals import (
    OutOfSampleComparisonDialog,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_view_model import (
    BackTestViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.backtest_fsm_matrix import (
    BacktestRunConfig,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.report_comparison_snapshot import (
    ReportComparisonSnapshot,
)

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


def _trade(pnl: float) -> Trade:
    return Trade(
        symbol="BTCUSDT",
        entry_time=_T0,
        entry_price=100.0,
        exit_time=_T0 + timedelta(hours=1),
        exit_price=100.0 + pnl,
        quantity=1.0,
        pnl=pnl,
        pnl_percent=pnl / 10_000.0 * 100.0,
        fees_paid=0.0,
    )


def _result(final_pnl: float = 500.0) -> BacktestResult:
    """`net_profit_percent` is trade-derived, not equity-curve-derived
    (`BacktestMetrics.compute()` returns all-zero metrics for an empty
    trades list) — a real trade with `pnl=final_pnl` is required for the
    overfit-divergence tests below to see a nonzero percentage at all."""
    return BacktestResult.compute(
        symbol="BTCUSDT",
        initial_balance=10_000.0,
        final_balance=10_000.0 + final_pnl,
        trades=[_trade(final_pnl)],
        equity_curve=[
            (_T0, 10_000.0),
            (_T0 + timedelta(hours=1), 10_000.0 + final_pnl),
        ],
    )


def _result_with_validation(validation: OutOfSampleValidation) -> BacktestResult:
    base = _result()
    return BacktestResult(
        symbol=base.symbol,
        initial_balance=base.initial_balance,
        final_balance=base.final_balance,
        trades=base.trades,
        equity_curve=base.equity_curve,
        metrics=base.metrics,
        out_of_sample=validation,
    )


def _snapshot(result: BacktestResult) -> ReportComparisonSnapshot:
    return ReportComparisonSnapshot(run_config=_run_config(), result=result)


def test_no_run_yet_shows_the_no_data_message_without_crashing(qapp):
    vm = BackTestViewModel()
    dialog = OutOfSampleComparisonDialog(vm)
    dialog.open_dialog()
    qapp.processEvents()

    assert dialog.isVisible() is True
    assert "not computed" in dialog._description_label.text()
    assert dialog._tree.topLevelItemCount() == 0
    dialog.close()


def test_a_run_without_out_of_sample_validation_shows_the_no_data_message(qapp):
    """A result exists but its own `out_of_sample` is `None` — too little
    data to split, or an older run — is not the same as no run at all, but
    reads with the same friendly message rather than crashing on `.result
    .out_of_sample.in_sample_ratio`."""
    vm = BackTestViewModel()
    vm.run_result.set_comparison_snapshot(_snapshot(_result()))
    dialog = OutOfSampleComparisonDialog(vm)
    dialog.open_dialog()
    qapp.processEvents()

    assert "not computed" in dialog._description_label.text()
    dialog.close()


def test_a_validated_run_renders_the_split_and_metrics_table(qapp):
    validation = OutOfSampleValidation(
        in_sample=_result(final_pnl=1000.0),
        out_of_sample=_result(final_pnl=500.0),
        in_sample_ratio=0.7,
    )
    vm = BackTestViewModel()
    vm.run_result.set_comparison_snapshot(
        _snapshot(_result_with_validation(validation))
    )
    dialog = OutOfSampleComparisonDialog(vm)
    dialog.open_dialog()
    qapp.processEvents()

    assert "70%" in dialog._description_label.text()
    assert dialog._tree.topLevelItemCount() > 0
    dialog.close()


def test_high_divergence_shows_the_overfit_warning(qapp):
    validation = OutOfSampleValidation(
        in_sample=_result(final_pnl=5000.0),
        out_of_sample=_result(final_pnl=-100.0),
        in_sample_ratio=0.7,
    )
    vm = BackTestViewModel()
    vm.run_result.set_comparison_snapshot(
        _snapshot(_result_with_validation(validation))
    )
    dialog = OutOfSampleComparisonDialog(vm)
    dialog.open_dialog()
    qapp.processEvents()

    assert dialog._warning_label.isVisible()
    assert "overfitting" in dialog._warning_label.text().lower()
    dialog.close()


def test_low_divergence_hides_the_overfit_warning(qapp):
    validation = OutOfSampleValidation(
        in_sample=_result(final_pnl=500.0),
        out_of_sample=_result(final_pnl=480.0),
        in_sample_ratio=0.7,
    )
    vm = BackTestViewModel()
    vm.run_result.set_comparison_snapshot(
        _snapshot(_result_with_validation(validation))
    )
    dialog = OutOfSampleComparisonDialog(vm)
    dialog.open_dialog()
    qapp.processEvents()

    assert not dialog._warning_label.isVisible()
    dialog.close()


def test_statcardschanged_refreshes_an_already_open_dialog(qapp):
    validation = OutOfSampleValidation(
        in_sample=_result(final_pnl=1000.0),
        out_of_sample=_result(final_pnl=500.0),
        in_sample_ratio=0.7,
    )
    vm = BackTestViewModel()
    dialog = OutOfSampleComparisonDialog(vm)
    dialog.open_dialog()
    qapp.processEvents()

    vm.run_result.set_comparison_snapshot(
        _snapshot(_result_with_validation(validation))
    )
    vm.run_result.statCardsChanged.emit()
    qapp.processEvents()

    assert "not computed" not in dialog._description_label.text()
    dialog.close()


def test_the_close_button_closes_the_dialog(qapp):
    vm = BackTestViewModel()
    dialog = OutOfSampleComparisonDialog(vm)
    dialog.open_dialog()
    qapp.processEvents()

    dialog.findChild(QPushButton, "btnCloseOutOfSampleComparison").click()
    qapp.processEvents()

    assert not dialog.isVisible()
