"""
Tests for the Backtest Screen's presenter (BOT-022).

Threading contract mirrors DataManagementPresenter/DashboardPresenter:
- IThreadManager is resolved once in __init__.
- Background work is submitted as `self._run_backtest(config)` via
  thread_manager.submit — NOT as an inline closure.
- `_run_backtest` itself is called directly (as the thread pool would call
  it) to test the background path without spinning a real thread; because
  sender and receiver share a thread in these tests, the `_backtest*Signal`s
  it emits execute their connected slots synchronously, so the resulting
  view-model/FSM state can be asserted immediately after the call returns.

Uses a REAL StrategyRegistry (with one fake strategy registered) and a REAL
BackTestViewModel — both are plain state/config holders with no I/O — mocking
only the genuine external dependencies (IDispatcher, IThreadManager, IConfig).
"""

import os
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from Sagittarius_Elite_Warrior.src.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.backtest.run_static_backtest.command import (
    RunStaticBacktestCommand,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.backtest_metrics import (
    BacktestMetrics,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.domain.strategies.base_strategy import BaseStrategy
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.presentation.ui.constants import UIMode
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_presenter import (
    BackTestPresenter,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_run_config import (
    BacktestRunConfig,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_view import (
    BackTestView,
)

_T0 = datetime(2026, 1, 1, tzinfo=UTC)
_T1 = datetime(2026, 1, 2, tzinfo=UTC)


class _FakeStrategy(BaseStrategy):
    def decide(self, context):
        return self.hold()

    def build_indicators(self):
        return {}


def _make_result(with_trades: bool) -> BacktestResult:
    metrics = BacktestMetrics(
        net_profit=10.0 if with_trades else 0.0,
        net_profit_percent=1.0 if with_trades else 0.0,
        gross_profit=10.0 if with_trades else 0.0,
        gross_loss=0.0,
        max_drawdown_percent=0.0,
        total_closed_trades=1 if with_trades else 0,
        percent_profitable=100.0 if with_trades else 0.0,
        profit_factor=1.0,
        avg_trade=0.0,
        avg_winning_trade=0.0,
        avg_losing_trade=0.0,
        largest_winning_trade=0.0,
        largest_losing_trade=0.0,
    )
    trades = []
    if with_trades:
        from Sagittarius_Elite_Warrior.src.domain.backtesting.trade import Trade

        trades = [
            Trade(
                symbol="ETHUSDT",
                entry_time=_T0,
                entry_price=100.0,
                exit_time=_T1,
                exit_price=110.0,
                quantity=1.0,
                pnl=10.0,
                pnl_percent=10.0,
                fees_paid=0.0,
            )
        ]
    return BacktestResult(
        symbol="ETHUSDT",
        initial_balance=1000.0,
        final_balance=1000.0 + (10.0 if with_trades else 0.0),
        trades=trades,
        equity_curve=[(_T0, 1000.0), (_T1, 1000.0)],
        metrics=metrics,
    )


@pytest.fixture
def strategy_registry():
    registry = StrategyRegistry()
    registry.register("fake_strategy", _FakeStrategy)
    return registry


@pytest.fixture
def mock_thread_mgr():
    return Mock()


@pytest.fixture
def mock_dispatcher():
    return Mock()


@pytest.fixture
def mock_container(mock_thread_mgr, mock_dispatcher, strategy_registry):
    container = Mock()

    def resolve_mock(interface):
        from sagittarius_engine.interfaces.i_config import IConfig
        from sagittarius_engine.interfaces.i_dispatcher import IDispatcher
        from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

        if interface == IThreadManager:
            return mock_thread_mgr
        if interface == IDispatcher:
            return mock_dispatcher
        if interface == IConfig:
            mock_config = Mock()
            mock_config.get_all.return_value = {}
            mock_config.get.return_value = None
            return mock_config
        if interface == StrategyRegistry:
            return strategy_registry
        return Mock()

    container.resolve.side_effect = resolve_mock
    return container


@pytest.fixture
def presenter(qapp, mock_container, request):
    view = BackTestView()
    view.resize(1400, 800)
    view.show()
    qapp.processEvents()
    request.addfinalizer(view.deleteLater)
    return BackTestPresenter(view, mock_container)


@pytest.fixture
def view_model(presenter):
    return presenter._view_model


# ---------------------------------------------------------------------------
# Strategy options
# ---------------------------------------------------------------------------


def test_strategy_options_loaded_from_registry_on_init(view_model):
    assert view_model.strategyOptions == [
        {
            "key": "fake_strategy",
            "name": "Fake Strategy",
            "category": "",
            "description": "",
        }
    ]
    assert view_model.selectedStrategyKey == "fake_strategy"


# ---------------------------------------------------------------------------
# Validation / dispatch gating
# ---------------------------------------------------------------------------


def test_run_backtest_submits_background_task_and_locks_fsm(
    presenter, view_model, mock_thread_mgr
):
    view_model.requestRun()

    assert presenter.fsm.current_state == UIMode.LOCKED
    mock_thread_mgr.submit.assert_called_once()
    call_args = mock_thread_mgr.submit.call_args[0]
    assert call_args[0] == presenter._run_backtest
    config = call_args[1]
    assert isinstance(config, BacktestRunConfig)
    assert config.strategy_key == "fake_strategy"
    assert config.timeframe == TimeFrame("15m")
    assert config.initial_balance == 10000.0


def test_invalid_capital_is_rejected_without_submitting(
    presenter, view_model, mock_thread_mgr
):
    view_model.initialCapitalText = "not-a-number"

    view_model.requestRun()

    mock_thread_mgr.submit.assert_not_called()
    assert view_model.resultIsError is True
    assert presenter.fsm.current_state == UIMode.IDLE


def test_non_positive_capital_is_rejected(presenter, view_model, mock_thread_mgr):
    view_model.initialCapitalText = "0"

    view_model.requestRun()

    mock_thread_mgr.submit.assert_not_called()
    assert view_model.resultIsError is True


def test_custom_range_with_invalid_start_is_rejected(
    presenter, view_model, mock_thread_mgr
):
    view_model.timeRangePreset = "custom"
    view_model.customStartText = "not-a-date"

    view_model.requestRun()

    mock_thread_mgr.submit.assert_not_called()
    assert view_model.resultIsError is True


def test_custom_range_start_after_end_is_rejected(
    presenter, view_model, mock_thread_mgr
):
    view_model.timeRangePreset = "custom"
    view_model.customStartText = "2026-06-01 00:00"
    view_model.customEndText = "2026-01-01 00:00"

    view_model.requestRun()

    mock_thread_mgr.submit.assert_not_called()
    assert view_model.resultIsError is True


def test_run_backtest_ignored_while_already_running(
    presenter, view_model, mock_thread_mgr
):
    view_model.requestRun()
    mock_thread_mgr.reset_mock()

    view_model.requestRun()

    mock_thread_mgr.submit.assert_not_called()


# ---------------------------------------------------------------------------
# Background outcomes (calling _run_backtest directly, as the pool would)
# ---------------------------------------------------------------------------


def _lock_and_get_config(presenter, view_model) -> BacktestRunConfig:
    view_model.requestRun()
    assert presenter.fsm.current_state == UIMode.LOCKED
    return presenter._build_run_config() or BacktestRunConfig(
        strategy_key="fake_strategy",
        timeframe=TimeFrame("15m"),
        initial_balance=10000.0,
        start_time=None,
        end_time=None,
    )


def test_successful_run_with_trades_updates_view_model_and_unlocks(
    presenter, view_model, mock_dispatcher
):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.return_value = _make_result(with_trades=True)

    presenter._run_backtest(config)

    assert presenter.fsm.current_state == UIMode.IDLE
    assert view_model.resultIsError is False
    assert "ETHUSDT" in view_model.resultText
    assert "Closed trades: 1" in view_model.resultText


def test_dispatches_run_static_backtest_command_with_the_built_config(
    presenter, view_model, mock_dispatcher
):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.return_value = _make_result(with_trades=True)

    presenter._run_backtest(config)

    mock_dispatcher.dispatch.assert_called_once()
    handler_class, command = mock_dispatcher.dispatch.call_args[0]
    assert handler_class is RunStaticBacktestCommand
    assert command.symbol == "ETHUSDT"
    assert command.strategy_key == "fake_strategy"
    assert command.interval == TimeFrame("15m")
    assert command.initial_balance == 10000.0


def test_no_historical_data_reports_empty_message_and_unlocks(
    presenter, view_model, mock_dispatcher
):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.return_value = None

    presenter._run_backtest(config)

    assert presenter.fsm.current_state == UIMode.IDLE
    assert view_model.resultIsError is False
    assert "Không có dữ liệu" in view_model.resultText


def test_zero_trades_reports_empty_message_with_the_metrics(
    presenter, view_model, mock_dispatcher
):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.return_value = _make_result(with_trades=False)

    presenter._run_backtest(config)

    assert presenter.fsm.current_state == UIMode.IDLE
    assert view_model.resultIsError is False
    assert "không có giao dịch nào" in view_model.resultText
    assert "Closed trades: 0" in view_model.resultText


def test_dispatch_exception_reports_error_and_unlocks(
    presenter, view_model, mock_dispatcher
):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = RuntimeError("boom")

    presenter._run_backtest(config)

    assert presenter.fsm.current_state == UIMode.IDLE
    assert view_model.resultIsError is True
    assert "boom" in view_model.resultText


# ---------------------------------------------------------------------------
# QML rendering
# ---------------------------------------------------------------------------


def test_qml_documents_load_without_errors(presenter, qapp):
    qapp.processEvents()
    assert presenter.view.top_widget.errors() == []
    assert presenter.view.bottom_widget.errors() == []
    assert presenter.view.top_widget.rootObject() is not None
    assert presenter.view.bottom_widget.rootObject() is not None


def test_qml_run_button_click_requests_a_run(
    presenter, view_model, qml_item, qapp, mock_thread_mgr
):
    qapp.processEvents()
    root = presenter.view.top_widget.rootObject()

    qml_item(root, "btnRunBacktest").clicked.emit()
    qapp.processEvents()

    mock_thread_mgr.submit.assert_called_once()


def test_bot_params_button_is_disabled(presenter, qml_item, qapp):
    qapp.processEvents()
    root = presenter.view.top_widget.rootObject()

    assert qml_item(root, "btnBacktestBotParams").property("enabled") is False
