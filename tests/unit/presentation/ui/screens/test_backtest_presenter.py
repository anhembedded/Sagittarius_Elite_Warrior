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

from Sagittarius_Elite_Warrior.src.application.services.indicator_script_registry import (
    IndicatorScriptRegistry,
)
from Sagittarius_Elite_Warrior.src.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.backtest.run_static_backtest.command import (
    RunStaticBacktestCommand,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.get_historical_klines.query import (
    GetHistoricalKlinesQuery,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.sync.sync_market_data.command import (
    SyncMarketDataCommand,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.backtest_metrics import (
    BacktestMetrics,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.strategies.base_strategy import BaseStrategy
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.chart_type_renderer import (
    CANDLESTICK,
    LINE,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_presenter import (
    _FALLBACK_SYMBOL,
    BackTestPresenter,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_run_config import (
    BacktestRunConfig,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_state import (
    BacktestUiState,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_view import (
    BackTestView,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.chart_canvas_view import (
    ChartDisplayMode,
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


def _dispatch_stub(result: BacktestResult | None, klines: list | None = None):
    """`_run_backtest` dispatches 2 different commands (BacktestResult, then
    chart klines) — a single `mock.return_value` can't tell them apart, so
    tests that reach the chart-fetch step need this instead."""

    def side_effect(handler_class, command):
        if handler_class is RunStaticBacktestCommand:
            return result
        if handler_class is GetHistoricalKlinesQuery:
            return klines or []
        raise AssertionError(f"Unexpected dispatch: {handler_class}")

    return side_effect


@pytest.fixture
def strategy_registry():
    registry = StrategyRegistry()
    registry.register("fake_strategy", _FakeStrategy)
    return registry


@pytest.fixture
def indicator_script_registry():
    # Deliberately empty and REAL (not a Mock): IndicatorScriptRunner.rebuild()
    # then hits its own KeyError/on_error path for the unregistered
    # "ema_ribbon" key, exactly as it would for any stale key — no need to
    # register the real script just to prove the chart-data path is safe.
    return IndicatorScriptRegistry()


@pytest.fixture
def mock_thread_mgr():
    return Mock()


@pytest.fixture
def mock_dispatcher():
    return Mock()


@pytest.fixture
def mock_config():
    config = Mock()
    # Empty by default: BOT-058's fallback path (no DEFAULT_SYMBOLS/
    # DEFAULT_INTERVAL configured) — individual tests override
    # get_all.return_value to exercise the config-driven path instead.
    config.get_all.return_value = {}
    config.get.return_value = None
    return config


@pytest.fixture
def mock_container(
    mock_thread_mgr,
    mock_dispatcher,
    mock_config,
    strategy_registry,
    indicator_script_registry,
):
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
            return mock_config
        if interface == StrategyRegistry:
            return strategy_registry
        if interface == IndicatorScriptRegistry:
            return indicator_script_registry
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
# Config-driven default symbol/interval (BOT-058)
# ---------------------------------------------------------------------------


def test_reads_default_symbol_and_interval_from_config(
    qapp, mock_container, mock_config, request
):
    mock_config.get_all.return_value = {
        "DEFAULT_SYMBOLS": ["BTCUSDT"],
        "DEFAULT_INTERVAL": "5m",
    }
    view = BackTestView()
    request.addfinalizer(view.deleteLater)

    presenter = BackTestPresenter(view, mock_container)

    assert presenter._symbol == "BTCUSDT"
    assert presenter._view_model.selectedTimeframe == "5m"
    assert view.chart_cards[0].symbol == "BTCUSDT"


def test_empty_default_symbols_falls_back_to_a_default_symbol(
    qapp, mock_container, mock_config, request
):
    mock_config.get_all.return_value = {"DEFAULT_SYMBOLS": [], "DEFAULT_INTERVAL": ""}
    view = BackTestView()
    request.addfinalizer(view.deleteLater)

    presenter = BackTestPresenter(view, mock_container)

    assert presenter._symbol == _FALLBACK_SYMBOL


def test_missing_config_keys_fall_back_safely(
    qapp, mock_container, mock_config, request
):
    """A fresh install (Settings never opened) must not crash the screen."""
    mock_config.get_all.return_value = {}
    view = BackTestView()
    request.addfinalizer(view.deleteLater)

    presenter = BackTestPresenter(view, mock_container)

    assert presenter._symbol == _FALLBACK_SYMBOL
    assert presenter._view_model.selectedTimeframe == "1m"


def test_invalid_default_interval_keeps_the_view_models_own_default(
    qapp, mock_container, mock_config, request
):
    """A hand-edited user_config.json with a typo'd interval must not crash
    or silently apply a value the toolbar doesn't offer."""
    mock_config.get_all.return_value = {"DEFAULT_INTERVAL": "999x"}
    view = BackTestView()
    request.addfinalizer(view.deleteLater)

    presenter = BackTestPresenter(view, mock_container)

    assert presenter._view_model.selectedTimeframe == "1m"


def test_run_backtest_and_chart_fetch_use_the_config_driven_symbol(
    qapp, mock_container, mock_config, mock_dispatcher, request
):
    mock_config.get_all.return_value = {"DEFAULT_SYMBOLS": ["BTCUSDT"]}
    view = BackTestView()
    request.addfinalizer(view.deleteLater)
    presenter = BackTestPresenter(view, mock_container)
    view_model = presenter._view_model
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True), klines=_make_klines()
    )

    config = _lock_and_get_config(presenter, view_model)
    presenter._run_backtest(config)

    assert mock_dispatcher.dispatch.call_args_list, "dispatch was never called"
    for call in mock_dispatcher.dispatch.call_args_list:
        _handler_class, command = call[0]
        assert command.symbol == "BTCUSDT"


# ---------------------------------------------------------------------------
# Validation / dispatch gating
# ---------------------------------------------------------------------------


def test_run_backtest_submits_background_task_and_locks_fsm(
    presenter, view_model, mock_thread_mgr
):
    view_model.requestRun()

    assert presenter.fsm.current_state == BacktestUiState.RUNNING
    mock_thread_mgr.submit.assert_called_once()
    call_args = mock_thread_mgr.submit.call_args[0]
    assert call_args[0] == presenter._run_backtest
    config = call_args[1]
    assert isinstance(config, BacktestRunConfig)
    assert config.strategy_key == "fake_strategy"
    assert config.timeframe == TimeFrame("1m")
    assert config.initial_balance == 10000.0


def test_invalid_capital_is_rejected_without_submitting(
    presenter, view_model, mock_thread_mgr
):
    view_model.initialCapitalText = "not-a-number"

    view_model.requestRun()

    mock_thread_mgr.submit.assert_not_called()
    assert view_model.resultIsError is True
    assert presenter.fsm.current_state == BacktestUiState.IDLE


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
    assert presenter.fsm.current_state == BacktestUiState.RUNNING
    return presenter._build_run_config() or BacktestRunConfig(
        strategy_key="fake_strategy",
        timeframe=TimeFrame("1m"),
        initial_balance=10000.0,
        start_time=None,
        end_time=None,
    )


def test_successful_run_with_trades_updates_view_model_and_unlocks(
    presenter, view_model, mock_dispatcher
):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True)
    )

    presenter._run_backtest(config)

    assert presenter.fsm.current_state == BacktestUiState.IDLE
    assert view_model.resultIsError is False
    assert "ETHUSDT" in view_model.resultText
    assert "Closed trades: 1" in view_model.resultText
    assert len(view_model.primaryStatCards) == 4
    assert len(view_model.extendedStatCards) == 8


def test_dispatches_run_static_backtest_command_with_the_built_config(
    presenter, view_model, mock_dispatcher
):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True)
    )

    presenter._run_backtest(config)

    # First call is the backtest itself — the chart's own klines fetch
    # (GetHistoricalKlinesQuery) happens after, tested separately below.
    handler_class, command = mock_dispatcher.dispatch.call_args_list[0][0]
    assert handler_class is RunStaticBacktestCommand
    assert command.symbol == "ETHUSDT"
    assert command.strategy_key == "fake_strategy"
    assert command.interval == TimeFrame("1m")
    assert command.initial_balance == 10000.0


def test_no_historical_data_reports_empty_message_and_unlocks(
    presenter, view_model, mock_dispatcher
):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.return_value = None

    presenter._run_backtest(config)

    assert presenter.fsm.current_state == BacktestUiState.IDLE
    assert view_model.resultIsError is False
    assert "Không có dữ liệu" in view_model.resultText
    # BOT-059: "no data at all" is exactly the case "Đồng bộ ngay" exists for.
    assert view_model.needsDataSync is True
    assert presenter._last_no_data_config is config


def test_zero_trades_reports_empty_message_with_the_metrics(
    presenter, view_model, mock_dispatcher
):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=False)
    )

    presenter._run_backtest(config)

    assert presenter.fsm.current_state == BacktestUiState.IDLE
    assert view_model.resultIsError is False
    assert "không có giao dịch nào" in view_model.resultText
    assert "Closed trades: 0" in view_model.resultText
    # BOT-055: 0 trades still populates the 4 cards (all reading 0), not an
    # empty panel — only "no historical data at all" clears it.
    assert len(view_model.primaryStatCards) == 4
    # BOT-059: 0 trades is a real result, not "no data" — must not offer sync.
    assert view_model.needsDataSync is False


def test_dispatch_exception_reports_error_and_unlocks(
    presenter, view_model, mock_dispatcher
):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = RuntimeError("boom")

    presenter._run_backtest(config)

    assert presenter.fsm.current_state == BacktestUiState.IDLE
    assert view_model.resultIsError is True
    assert "boom" in view_model.resultText


# ---------------------------------------------------------------------------
# "Đồng bộ ngay" (BOT-059)
# ---------------------------------------------------------------------------


def _run_to_no_data(presenter, view_model, mock_dispatcher) -> BacktestRunConfig:
    """Drives the presenter into the "no historical data, needsDataSync=True"
    state every sync test starts from."""
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.return_value = None
    presenter._run_backtest(config)
    mock_dispatcher.dispatch.reset_mock()
    return config


def test_request_sync_ignored_without_a_cached_no_data_config(
    presenter, view_model, mock_thread_mgr
):
    view_model.requestSync()

    mock_thread_mgr.submit.assert_not_called()
    assert presenter.fsm.current_state == BacktestUiState.IDLE


def test_request_sync_transitions_to_syncing_and_submits_background_task(
    presenter, view_model, mock_dispatcher, mock_thread_mgr
):
    config = _run_to_no_data(presenter, view_model, mock_dispatcher)
    mock_thread_mgr.reset_mock()

    view_model.requestSync()

    assert presenter.fsm.current_state == BacktestUiState.SYNCING
    mock_thread_mgr.submit.assert_called_once()
    call_args = mock_thread_mgr.submit.call_args[0]
    assert call_args[0] == presenter._run_sync
    assert call_args[1] is config


def test_request_sync_ignored_while_a_backtest_is_already_running(
    presenter, view_model, mock_dispatcher, mock_thread_mgr
):
    _run_to_no_data(presenter, view_model, mock_dispatcher)
    view_model.requestRun()  # IDLE -> RUNNING again
    mock_thread_mgr.reset_mock()

    view_model.requestSync()

    mock_thread_mgr.submit.assert_not_called()


def test_run_sync_dispatches_sync_market_data_command_for_the_no_data_config(
    presenter, view_model, mock_dispatcher
):
    config = _run_to_no_data(presenter, view_model, mock_dispatcher)
    view_model.requestSync()
    mock_dispatcher.dispatch.return_value = None  # sync itself has no return value

    presenter._run_sync(config)

    handler_class, command = mock_dispatcher.dispatch.call_args_list[0][0]
    assert handler_class is SyncMarketDataCommand
    assert command.symbols == [presenter._symbol]
    assert command.interval == config.timeframe


def test_sync_success_clears_the_flag_and_auto_resubmits_the_backtest(
    presenter, view_model, mock_dispatcher, mock_thread_mgr
):
    config = _run_to_no_data(presenter, view_model, mock_dispatcher)
    view_model.requestSync()
    mock_thread_mgr.reset_mock()
    # _run_sync only dispatches SyncMarketDataCommand — the resubmitted
    # RunStaticBacktestCommand is never actually dispatched in this test
    # since mock_thread_mgr.submit is a Mock, not a real thread pool.
    mock_dispatcher.dispatch.side_effect = None
    mock_dispatcher.dispatch.return_value = None

    presenter._run_sync(config)

    assert view_model.needsDataSync is False
    assert presenter._last_no_data_config is None
    # Auto-resubmitted straight into RUNNING, no click needed.
    assert presenter.fsm.current_state == BacktestUiState.RUNNING
    mock_thread_mgr.submit.assert_called_once()
    call_args = mock_thread_mgr.submit.call_args[0]
    assert call_args[0] == presenter._run_backtest


def test_sync_success_resubmits_with_the_toolbars_current_fields(
    presenter, view_model, mock_dispatcher, mock_thread_mgr
):
    """The user may edit the toolbar while the sync is in flight — the
    resubmitted run must use those CURRENT fields, not the stale cached
    config that triggered the sync."""
    config = _run_to_no_data(presenter, view_model, mock_dispatcher)
    view_model.requestSync()
    view_model.initialCapitalText = "500"
    mock_thread_mgr.reset_mock()
    # _run_sync only dispatches SyncMarketDataCommand — the resubmitted
    # RunStaticBacktestCommand is never actually dispatched in this test
    # since mock_thread_mgr.submit is a Mock, not a real thread pool.
    mock_dispatcher.dispatch.side_effect = None
    mock_dispatcher.dispatch.return_value = None

    presenter._run_sync(config)

    resubmitted_config = mock_thread_mgr.submit.call_args[0][1]
    assert resubmitted_config.initial_balance == 500.0


def test_sync_failure_keeps_the_flag_and_returns_to_idle(
    presenter, view_model, mock_dispatcher, mock_thread_mgr
):
    config = _run_to_no_data(presenter, view_model, mock_dispatcher)
    view_model.requestSync()
    mock_thread_mgr.reset_mock()
    mock_dispatcher.dispatch.side_effect = RuntimeError("sync boom")

    presenter._run_sync(config)

    assert presenter.fsm.current_state == BacktestUiState.IDLE
    assert view_model.needsDataSync is True
    assert presenter._last_no_data_config is config
    assert view_model.resultIsError is True
    assert "sync boom" in view_model.resultText
    mock_thread_mgr.submit.assert_not_called()


def test_qml_sync_button_only_visible_after_no_data_and_click_requests_sync(
    presenter, view_model, mock_dispatcher, qml_item, qapp, mock_thread_mgr
):
    qapp.processEvents()
    root = presenter.view.top_widget.rootObject()
    assert qml_item(root, "btnRequestSync").property("visible") is False

    _run_to_no_data(presenter, view_model, mock_dispatcher)
    qapp.processEvents()
    mock_thread_mgr.reset_mock()

    assert qml_item(root, "btnRequestSync").property("visible") is True
    qml_item(root, "btnRequestSync").clicked.emit()
    qapp.processEvents()

    mock_thread_mgr.submit.assert_called_once()
    assert mock_thread_mgr.submit.call_args[0][0] == presenter._run_sync


# ---------------------------------------------------------------------------
# Stat cards (BOT-055)
# ---------------------------------------------------------------------------


def test_qml_renders_a_metric_card_per_primary_stat_card_after_a_run(
    presenter, view_model, qml_item, qapp, mock_dispatcher
):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True)
    )

    presenter._run_backtest(config)
    qapp.processEvents()

    root = presenter.view.top_widget.rootObject()
    card = qml_item(root, "cardMetric_0")
    assert card is not None
    assert card.property("value") != ""


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


# ---------------------------------------------------------------------------
# Chart canvas (BOT-056)
# ---------------------------------------------------------------------------


def _make_klines(count: int = 3) -> list[MarketData]:
    return [
        MarketData(
            symbol="ETHUSDT",
            interval="1m",
            open_time=_T0,
            open_price=100.0 + i,
            high_price=105.0 + i,
            low_price=95.0 + i,
            close_price=102.0 + i,
            volume=10.0,
            close_time=_T0,
            quote_asset_volume=0.0,
            number_of_trades=1,
            taker_buy_base_asset_volume=0.0,
            taker_buy_quote_asset_volume=0.0,
        )
        for i in range(count)
    ]


def test_successful_run_fetches_klines_and_renders_the_ohlc_chart(
    presenter, view_model, mock_dispatcher
):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True), klines=_make_klines()
    )

    presenter._run_backtest(config)

    assert len(presenter.view._last_klines) == 3
    assert presenter.view.chart_cards[0]._raw_history
    assert presenter.view.chart_cards[0].chart_type_renderer.chart_type == CANDLESTICK


def test_no_klines_leaves_the_chart_unrendered_without_crashing(
    presenter, view_model, mock_dispatcher
):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True)
    )

    presenter._run_backtest(config)

    assert presenter.view._last_klines == []


def test_switching_to_equity_mode_renders_a_line_from_the_equity_curve(
    presenter, view_model, mock_dispatcher
):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True), klines=_make_klines()
    )
    presenter._run_backtest(config)

    presenter.view.set_chart_mode(ChartDisplayMode.EQUITY)

    assert presenter.view.chart_cards[0].chart_type_renderer.chart_type == LINE


def test_switching_to_both_mode_adds_an_equity_subplot(
    presenter, view_model, mock_dispatcher
):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True), klines=_make_klines()
    )
    presenter._run_backtest(config)

    presenter.view.set_chart_mode(ChartDisplayMode.BOTH)

    assert presenter.view._equity_subplot_added is True
    assert presenter.view.chart_cards[0].chart_type_renderer.chart_type == CANDLESTICK


def test_switching_away_from_both_mode_removes_the_equity_subplot(
    presenter, view_model, mock_dispatcher
):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True), klines=_make_klines()
    )
    presenter._run_backtest(config)
    presenter.view.set_chart_mode(ChartDisplayMode.BOTH)

    presenter.view.set_chart_mode(ChartDisplayMode.OHLC)

    assert presenter.view._equity_subplot_added is False


def test_ema_toggle_is_a_no_op_when_the_script_is_not_registered(
    presenter, view_model, mock_dispatcher
):
    """ema_ribbon isn't in the (deliberately empty) test registry — proves
    the toggle path degrades safely instead of crashing on a missing key."""
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True), klines=_make_klines()
    )
    presenter._run_backtest(config)

    presenter.view.chart_controls.sig_ema_toggled.emit(False)  # must not raise


def test_clear_from_chart_is_called_before_each_new_run_not_after(
    presenter, view_model
):
    """Regression test (found by running the app): clearing the previous
    run's chart overlays must happen synchronously in _on_run_backtest (main
    thread, before the background run even starts). Calling it later, after
    IndicatorScriptRunner.rebuild() has already replaced `.active` on the
    background thread, is a no-op — the old EMA curves/legend entries pile
    up run after run instead of being replaced."""
    presenter._chart_script_runner.clear_from_chart = Mock()

    view_model.requestRun()
    assert presenter._chart_script_runner.clear_from_chart.call_count == 1

    presenter.fsm.transition_to(BacktestUiState.IDLE)
    view_model.requestRun()
    assert presenter._chart_script_runner.clear_from_chart.call_count == 2


def test_mode_buttons_switch_the_chart_mode_end_to_end(
    presenter, view_model, mock_dispatcher, qapp
):
    """Native QPushButton click -> BacktestChartControls signal -> Presenter
    slot -> View render, with no QML/ViewModel involved."""
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True), klines=_make_klines()
    )
    presenter._run_backtest(config)

    presenter.view.chart_controls._mode_buttons[ChartDisplayMode.EQUITY].click()
    qapp.processEvents()

    assert presenter.view.chart_cards[0].chart_type_renderer.chart_type == LINE
    assert presenter.view.chart_controls._trade_flags_check.isEnabled() is False


def test_trade_flags_toggle_draws_and_clears_markers(
    presenter, view_model, mock_dispatcher
):
    config = _lock_and_get_config(presenter, view_model)
    mock_dispatcher.dispatch.side_effect = _dispatch_stub(
        _make_result(with_trades=True), klines=_make_klines()
    )
    presenter._run_backtest(config)
    card = presenter.view.chart_cards[0]

    presenter.view.set_trade_flags_visible(False)
    assert card.indicators._marker_layer._items.get("backtest_trades", []) == []

    presenter.view.set_trade_flags_visible(True)
    assert len(card.indicators._marker_layer._items.get("backtest_trades", [])) == 2
