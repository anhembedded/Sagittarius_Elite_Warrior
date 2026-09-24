"""`ReportComparisonDialog` against a real `BackTestViewModel` (`BOT-115D`).

What only a test building the real composition root can prove: that
Column A really reads `run_result.comparison_snapshot()`, that loading a
real `.sagi-report.json` file off disk fills Column B, and that a
`statCardsChanged` emission (the same signal the Presenter fires alongside
`set_comparison_snapshot`) refreshes an already-open dialog.

The comparison math itself — diff text, metric tone, equity
normalization — is `logic/test_report_comparison_rules.py`'s, with no
dialog in sight.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from PySide6.QtWidgets import QPushButton
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.trade import Trade
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_modals import (
    ReportComparisonDialog,
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
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.report_export import (
    build_backtest_report,
    write_backtest_report,
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


def _trade(pnl: float = 100.0) -> Trade:
    return Trade(
        symbol="BTCUSDT",
        entry_time=_T0,
        entry_price=100.0,
        exit_time=_T0 + timedelta(hours=1),
        exit_price=110.0,
        quantity=1.0,
        pnl=pnl,
        pnl_percent=1.0,
        fees_paid=0.1,
    )


def _result(
    initial_balance: float = 10_000.0, final_pnl: float = 500.0
) -> BacktestResult:
    return BacktestResult.compute(
        symbol="BTCUSDT",
        initial_balance=initial_balance,
        final_balance=initial_balance + final_pnl,
        trades=[_trade(final_pnl)],
        equity_curve=[
            (_T0, initial_balance),
            (_T0 + timedelta(hours=1), initial_balance + final_pnl),
        ],
    )


def _snapshot(**overrides) -> ReportComparisonSnapshot:
    return ReportComparisonSnapshot(
        run_config=overrides.get("run_config", _run_config()),
        result=overrides.get("result", _result()),
    )


def test_no_run_yet_shows_the_empty_column_a_message_without_crashing(qapp):
    vm = BackTestViewModel()
    dialog = ReportComparisonDialog(vm)
    dialog.open_dialog()
    qapp.processEvents()

    assert dialog.isVisible() is True
    assert "Run a backtest first" in dialog._column_a_label.text()
    assert dialog._tree.topLevelItemCount() == 0
    dialog.close()


def test_column_a_renders_the_view_models_retained_snapshot(qapp):
    vm = BackTestViewModel()
    vm.run_result.set_comparison_snapshot(_snapshot())
    dialog = ReportComparisonDialog(vm)
    dialog.open_dialog()
    qapp.processEvents()

    assert "BTCUSDT" in dialog._column_a_label.text()
    assert "Load a report" in dialog._column_b_label.text()
    dialog.close()


def test_statcardschanged_refreshes_an_already_open_dialog(qapp):
    vm = BackTestViewModel()
    dialog = ReportComparisonDialog(vm)
    dialog.open_dialog()
    qapp.processEvents()

    vm.run_result.set_comparison_snapshot(_snapshot())
    vm.run_result.statCardsChanged.emit()
    qapp.processEvents()

    assert "Run a backtest first" not in dialog._column_a_label.text()
    dialog.close()


def test_loading_a_real_report_file_via_the_button_fills_column_b_and_the_metrics_table(
    qapp, tmp_path
):
    """Drives the real "Load report to compare…" button — the same path a
    user click takes — rather than poking `_loaded_b` directly, so this
    proves the actual file-picker wiring, not just the render logic."""
    vm = BackTestViewModel()
    vm.run_result.set_comparison_snapshot(_snapshot(result=_result(final_pnl=500.0)))
    dialog = ReportComparisonDialog(vm)
    dialog.open_dialog()
    qapp.processEvents()

    other_config = _run_config(symbol="ETHUSDT")
    other_result = _result(final_pnl=-200.0)
    report = build_backtest_report(
        other_config,
        other_result,
        app_version="1.0.0",
        engine_version="2.0.0",
        created_at=_T0,
    )
    path = tmp_path / "baseline.sagi-report.json"
    write_backtest_report(report, str(path))

    with patch(
        "Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_modals."
        "report_comparison_dialog.QFileDialog.getOpenFileName",
        return_value=(str(path), ""),
    ):
        dialog.findChild(QPushButton, "btnLoadComparisonReport").click()
    qapp.processEvents()

    assert "baseline.sagi-report.json" in dialog._column_b_label.text()
    assert dialog._tree.topLevelItemCount() > 0
    assert "different markets" in dialog._warning_label.text()
    assert dialog._warning_label.isVisible()
    dialog.close()


def test_cancelling_the_file_picker_leaves_column_b_unfilled(qapp):
    vm = BackTestViewModel()
    dialog = ReportComparisonDialog(vm)
    dialog.open_dialog()
    qapp.processEvents()

    with patch(
        "Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_modals."
        "report_comparison_dialog.QFileDialog.getOpenFileName",
        return_value=("", ""),
    ):
        dialog.findChild(QPushButton, "btnLoadComparisonReport").click()
    qapp.processEvents()

    assert "Load a report" in dialog._column_b_label.text()
    dialog.close()


def test_loading_a_malformed_file_shows_an_error_instead_of_crashing(qapp, tmp_path):
    vm = BackTestViewModel()
    dialog = ReportComparisonDialog(vm)
    dialog.open_dialog()
    qapp.processEvents()

    path = tmp_path / "broken.sagi-report.json"
    path.write_bytes(b"not json at all")

    with patch(
        "Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_modals."
        "report_comparison_dialog.QFileDialog.getOpenFileName",
        return_value=(str(path), ""),
    ):
        dialog.findChild(QPushButton, "btnLoadComparisonReport").click()
    qapp.processEvents()

    assert "Load a report" not in dialog._column_b_label.text()
    assert dialog._tree.topLevelItemCount() == 0
    dialog.close()


def test_the_close_button_closes_the_dialog(qapp):
    vm = BackTestViewModel()
    dialog = ReportComparisonDialog(vm)
    dialog.open_dialog()
    qapp.processEvents()

    dialog.findChild(QPushButton, "btnCloseComparison").click()
    qapp.processEvents()

    assert not dialog.isVisible()
