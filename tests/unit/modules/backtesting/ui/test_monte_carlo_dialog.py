"""`MonteCarloDialog` against a real `BackTestViewModel` (`BOT-107B`).

What only a test building the real composition root can prove: that the
dialog reads `run_result.comparison_snapshot()` for its trade count, that
clicking "Run simulation" reaches the real `requestRunMonteCarlo` signal
(not just a private method), and that `monteCarloResultChanged` refreshes
an already-open dialog — the same wiring shape
`test_out_of_sample_comparison_dialog.py` already proves for its own
sibling dialog.

The comparison math itself (summary lines, histogram bucketing, spaghetti
series) is `logic/test_monte_carlo_rules.py`'s, with no dialog in sight.
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
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.monte_carlo_simulation import (
    MonteCarloSimulationResult,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.trade import Trade
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_modals import (
    MonteCarloDialog,
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


def _run_config() -> BacktestRunConfig:
    return BacktestRunConfig(
        strategy_key="ema_crossover",
        timeframe=TimeFrame.FIVE_MINUTES,
        initial_balance=10_000.0,
        start_time=_T0 - timedelta(days=30),
        end_time=_T0,
        symbol="BTCUSDT",
    )


def _trade(pnl: float) -> Trade:
    return Trade(
        symbol="BTCUSDT",
        entry_time=_T0,
        entry_price=100.0,
        exit_time=_T0 + timedelta(hours=1),
        exit_price=100.0 + pnl,
        quantity=1.0,
        pnl=pnl,
        pnl_percent=pnl / 100.0,
        fees_paid=0.0,
    )


def _result(trade_count: int) -> BacktestResult:
    trades = [_trade(10.0) for _ in range(trade_count)]
    return BacktestResult.compute(
        symbol="BTCUSDT",
        initial_balance=10_000.0,
        final_balance=10_000.0 + 10.0 * trade_count,
        trades=trades,
        equity_curve=[(_T0, 10_000.0)],
    )


def _snapshot(trade_count: int) -> ReportComparisonSnapshot:
    return ReportComparisonSnapshot(
        run_config=_run_config(), result=_result(trade_count)
    )


def _simulation_result() -> MonteCarloSimulationResult:
    return MonteCarloSimulationResult(
        iterations=5000,
        median_return_percent=8.0,
        p95_max_drawdown_percent=20.0,
        p99_max_drawdown_percent=30.0,
        risk_of_ruin_50_percent=1.5,
        risk_of_ruin_100_percent=0.0,
        max_drawdowns_percent=(5.0, 10.0, 20.0),
        sample_equity_curves=((10_000.0, 10_100.0),),
    )


def test_no_run_yet_shows_the_empty_state_and_disables_the_run_button(qapp):
    vm = BackTestViewModel()
    dialog = MonteCarloDialog(vm)
    dialog.open_dialog()
    qapp.processEvents()

    assert dialog.isVisible() is True
    assert "Run a backtest first" in dialog._description_label.text()
    assert not dialog._btn_run.isEnabled()
    dialog.close()


def test_too_few_trades_shows_the_not_enough_trades_message(qapp):
    vm = BackTestViewModel()
    vm.run_result.set_comparison_snapshot(_snapshot(trade_count=1))
    dialog = MonteCarloDialog(vm)
    dialog.open_dialog()
    qapp.processEvents()

    assert "too few trades" in dialog._description_label.text()
    assert not dialog._btn_run.isEnabled()
    dialog.close()


def test_enough_trades_enables_the_run_button(qapp):
    vm = BackTestViewModel()
    vm.run_result.set_comparison_snapshot(_snapshot(trade_count=5))
    dialog = MonteCarloDialog(vm)
    dialog.open_dialog()
    qapp.processEvents()

    assert dialog._btn_run.isEnabled()
    assert dialog._spin_iterations.isEnabled()
    dialog.close()


def test_clicking_run_reaches_the_real_view_model_signal_with_the_chosen_iterations(
    qapp,
):
    """Wiring test (`testing-rule.md` §E12): drives the real button click
    rather than calling a private method, so removing the `.connect(...)`
    line in `_build_controls_row()` makes this fail."""
    vm = BackTestViewModel()
    vm.run_result.set_comparison_snapshot(_snapshot(trade_count=5))
    dialog = MonteCarloDialog(vm)
    dialog.open_dialog()
    qapp.processEvents()
    received: list[int] = []
    vm.runMonteCarloRequested.connect(received.append)
    dialog._spin_iterations.setValue(7000)

    dialog.findChild(QPushButton, "btnRunMonteCarloSimulation").click()

    assert received == [7000]
    assert not dialog._btn_run.isEnabled()
    dialog.close()


def test_a_completed_result_renders_the_summary_and_feeds_both_charts(qapp):
    vm = BackTestViewModel()
    vm.run_result.set_comparison_snapshot(_snapshot(trade_count=5))
    dialog = MonteCarloDialog(vm)
    dialog.open_dialog()
    qapp.processEvents()

    vm.run_result.set_monte_carlo_result(_simulation_result())
    qapp.processEvents()

    assert "5,000" in dialog._summary_label.text()
    assert dialog._btn_run.isEnabled()
    assert len(dialog._spaghetti_chart._curves) == 1
    assert dialog._histogram._bars.opts["height"]
    dialog.close()


def test_a_failed_run_shows_the_error_and_clears_the_charts(qapp):
    vm = BackTestViewModel()
    vm.run_result.set_comparison_snapshot(_snapshot(trade_count=5))
    dialog = MonteCarloDialog(vm)
    dialog.open_dialog()
    qapp.processEvents()
    vm.run_result.set_monte_carlo_result(_simulation_result())
    qapp.processEvents()

    vm.run_result.set_monte_carlo_error("boom")
    qapp.processEvents()

    assert "boom" in dialog._summary_label.text()
    assert dialog._spaghetti_chart._curves == []
    dialog.close()


def test_clearing_the_result_reverts_the_dialog_to_its_empty_summary(qapp):
    vm = BackTestViewModel()
    vm.run_result.set_comparison_snapshot(_snapshot(trade_count=5))
    dialog = MonteCarloDialog(vm)
    dialog.open_dialog()
    qapp.processEvents()
    vm.run_result.set_monte_carlo_result(_simulation_result())
    qapp.processEvents()

    vm.run_result.clear_monte_carlo_result()
    qapp.processEvents()

    assert dialog._summary_label.text() == ""
    assert dialog._spaghetti_chart._curves == []
    dialog.close()


def test_the_close_button_closes_the_dialog(qapp):
    vm = BackTestViewModel()
    dialog = MonteCarloDialog(vm)
    dialog.open_dialog()
    qapp.processEvents()

    dialog.findChild(QPushButton, "btnCloseMonteCarlo").click()
    qapp.processEvents()

    assert not dialog.isVisible()
