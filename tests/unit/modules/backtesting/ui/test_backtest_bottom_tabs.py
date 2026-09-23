from __future__ import annotations

from unittest.mock import MagicMock

from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.events.backtest_completed_event import (
    BacktestCompletedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.events.backtest_failed_event import (
    BacktestFailedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_trade_logs_panel import (
    BackTestTradeLogsPanel,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_view_model import (
    BackTestViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.backtest_chart_host import (
    BacktestChartHostFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.signal_generated_event import (
    SignalGeneratedEvent,
)


def test_backtest_view_model_bottom_tabs_and_log_model(qapp) -> None:
    vm = BackTestViewModel()
    assert vm.activeBottomTab == "trades"
    assert vm.logModel is not None
    assert vm.log_model is not None

    tab_changed_spy = MagicMock()
    vm.activeBottomTabChanged.connect(tab_changed_spy)

    vm.setActiveBottomTab("logs")
    assert vm.activeBottomTab == "logs"
    assert tab_changed_spy.call_count == 1

    # Setting to same value does not emit
    vm.setActiveBottomTab("logs")
    assert tab_changed_spy.call_count == 1

    vm.setActiveBottomTab("trades")
    assert vm.activeBottomTab == "trades"
    assert tab_changed_spy.call_count == 2


def test_backtest_bottom_tabs_switch_between_trades_and_logs(qapp) -> None:
    vm = BackTestViewModel()
    panel = BackTestTradeLogsPanel(vm)

    assert panel._tab_bar.objectName() == "bottomTabBar"
    assert panel._trades_tab.objectName() == "tradeLogsTabContent"
    assert panel._log_panel.objectName() == "backtestLogPanel"

    # Tab 1 (trades) visible initially, log panel hidden. `isVisibleTo(panel)`
    # rather than `isVisible()` — this test never calls `panel.show()`, and
    # `isVisible()` stays False regardless of `setVisible()` until the whole
    # ancestor chain is actually shown (see Sidebar/Overlay tests for the
    # same gotcha).
    assert panel._trades_tab.isVisibleTo(panel)
    assert not panel._log_panel.isVisibleTo(panel)

    # Switch to logs tab
    vm.setActiveBottomTab("logs")
    qapp.processEvents()
    assert not panel._trades_tab.isVisibleTo(panel)
    assert panel._log_panel.isVisibleTo(panel)

    # Switch back to trades tab
    vm.setActiveBottomTab("trades")
    qapp.processEvents()
    assert panel._trades_tab.isVisibleTo(panel)
    assert not panel._log_panel.isVisibleTo(panel)


def test_backtest_bottom_tabs_include_drawdown_and_returns(qapp) -> None:
    """`BOT-106D` — two more tabs, mutually exclusive with the other two."""
    vm = BackTestViewModel()
    panel = BackTestTradeLogsPanel(vm)

    assert not panel._drawdown_tab.isVisibleTo(panel)
    assert not panel._returns_tab.isVisibleTo(panel)

    vm.setActiveBottomTab("drawdown")
    qapp.processEvents()
    assert panel._drawdown_tab.isVisibleTo(panel)
    assert not panel._trades_tab.isVisibleTo(panel)
    assert not panel._returns_tab.isVisibleTo(panel)
    assert not panel._log_panel.isVisibleTo(panel)

    vm.setActiveBottomTab("returns")
    qapp.processEvents()
    assert panel._returns_tab.isVisibleTo(panel)
    assert not panel._drawdown_tab.isVisibleTo(panel)


def test_backtest_bottom_tabs_forward_drawdown_and_returns_data(qapp) -> None:
    """`BOT-106D` — the panel reads `run_result.drawdownPoints`/
    `.yearlyReturns` reactively, the same wiring `_sync_rows`/`trade_log`
    already uses for the trades tab."""
    vm = BackTestViewModel()
    panel = BackTestTradeLogsPanel(vm)

    vm.run_result.set_drawdown_points([{"t": 0.0, "v": -5.0}])
    qapp.processEvents()
    assert panel._drawdown_chart._plot_widget.isVisibleTo(panel._drawdown_chart)
    assert not panel._drawdown_chart._empty_label.isVisibleTo(panel._drawdown_chart)

    rows = [
        {"year": 2024, "months": [None] * 12, "ytdText": "+0.00%", "ytdColor": "#000"}
    ]
    vm.run_result.set_yearly_returns(rows)
    qapp.processEvents()
    assert panel._returns_heatmap._grid_container.isVisibleTo(panel._returns_heatmap)


def test_backtest_presenter_event_bus_handlers(qapp) -> None:
    from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_presenter import (
        BackTestPresenter,
    )
    from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_view import (
        BackTestView,
    )
    from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_catalog_service import (
        StrategyCatalogService,
    )
    from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_chart_overlay_service import (
        StrategyChartOverlayService,
    )
    from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_registry import (
        StrategyRegistry,
    )
    from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_strategy_catalog import (
        IStrategyCatalog,
    )
    from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_strategy_chart_overlay import (
        IStrategyChartOverlay,
    )
    from Sagittarius_Elite_Warrior.src.support.indicators.indicator_script_registry import (
        IndicatorScriptRegistry,
    )
    from sagittarius_engine.interfaces.i_config import IConfig
    from sagittarius_engine.interfaces.i_event_bus import IEventBus
    from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

    mock_config = MagicMock(spec=IConfig)
    mock_config.get_all.return_value = {}
    mock_config.get.return_value = True  # dev mode = True

    mock_event_bus = MagicMock(spec=IEventBus)
    mock_threads = MagicMock(spec=IThreadManager)
    strategy_reg = StrategyRegistry()
    script_reg = IndicatorScriptRegistry()

    container = MagicMock()

    def resolve_side_effect(interface):
        if interface == IConfig:
            return mock_config
        if interface == IEventBus:
            return mock_event_bus
        if interface == IThreadManager:
            return mock_threads
        if interface == StrategyRegistry:
            return strategy_reg
        if interface == IStrategyCatalog:
            return StrategyCatalogService(strategy_reg)
        if interface == IStrategyChartOverlay:
            return StrategyChartOverlayService(strategy_reg)
        if interface == IndicatorScriptRegistry:
            return script_reg
        if interface == BacktestChartHostFactory:
            return BacktestChartHostFactory()
        return MagicMock()

    container.resolve.side_effect = resolve_side_effect

    view = BackTestView()
    presenter = BackTestPresenter(view, container)

    # Verify event subscriptions
    mock_event_bus.on.assert_any_call(
        BacktestCompletedEvent, presenter._handle_backtest_completed_event
    )
    mock_event_bus.on.assert_any_call(
        BacktestFailedEvent, presenter._handle_backtest_failed_event
    )
    mock_event_bus.on.assert_any_call(
        SignalGeneratedEvent, presenter._handle_signal_generated_event
    )

    # Test handling BacktestCompletedEvent
    mock_result = MagicMock()
    mock_result.trades = [MagicMock()]
    mock_result.duration = 0.5
    completed_event = BacktestCompletedEvent(result=mock_result)
    initial_log_count = presenter._view_model.log_model.rowCount()
    presenter._handle_backtest_completed_event(completed_event)
    assert presenter._view_model.log_model.rowCount() == initial_log_count + 1

    # Test handling BacktestFailedEvent
    failed_event = BacktestFailedEvent(reason="Network Timeout")
    presenter._handle_backtest_failed_event(failed_event)
    assert presenter._view_model.log_model.rowCount() == initial_log_count + 2

    from sagittarius_engine.extensions.pyside_mvc.QmlShared.log_list_model import (
        LogListModel,
    )

    # Test user UI selection events emitting logs
    current_count = presenter._view_model.log_model.rowCount()
    presenter._view_model.strategy_params.selectedStrategyKey = (
        "multi_ema_trend_follower"
    )
    assert presenter._view_model.log_model.rowCount() == current_count + 1
    idx = presenter._view_model.log_model.index(current_count, 0)
    assert "strategy" in presenter._view_model.log_model.data(
        idx, LogListModel.MessageRole
    )

    current_count = presenter._view_model.log_model.rowCount()
    presenter._view_model.selectedTimeframe = "15m"
    assert presenter._view_model.log_model.rowCount() == current_count + 1
    idx = presenter._view_model.log_model.index(current_count, 0)
    assert "15m" in presenter._view_model.log_model.data(idx, LogListModel.MessageRole)

    current_count = presenter._view_model.log_model.rowCount()
    presenter._view_model.initialCapitalText = "100000"
    assert presenter._view_model.log_model.rowCount() == current_count + 1
    idx = presenter._view_model.log_model.index(current_count, 0)
    assert "100,000" in presenter._view_model.log_model.data(
        idx, LogListModel.MessageRole
    )
