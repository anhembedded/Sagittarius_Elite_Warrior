from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDockWidget, QMainWindow
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.events.backtest_completed_event import (
    BacktestCompletedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.events.backtest_failed_event import (
    BacktestFailedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_trade_logs_panel import (
    BackTestTradeLogsPanel,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_view import (
    BackTestView,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_view_model import (
    BackTestViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.backtest_chart_host import (
    BacktestChartHostFactory,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.trade_log_row import (
    TradeLogRow,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.signal_generated_event import (
    SignalGeneratedEvent,
)


def test_backtest_view_model_has_a_log_model(qapp) -> None:
    vm = BackTestViewModel()
    assert vm.logModel is not None
    assert vm.log_model is not None


def test_the_bottom_docks_are_trades_drawdown_and_monthly_returns(qapp) -> None:
    """`EPIC-033L`: the panel's own tab bar (Trades, Drawdown, Returns) is
    three docks in the bottom area, tabbed, Trades in front. The run log is
    the Output pane's "Backtest" channel (`EPIC-033F`), never a tab."""
    vm = BackTestViewModel()
    view = BackTestView()
    view.set_view_model(vm)
    surface = view.findChild(QMainWindow)
    bottom = [
        dock.windowTitle()
        for dock in view.findChildren(QDockWidget)
        if surface.dockWidgetArea(dock) is Qt.DockWidgetArea.BottomDockWidgetArea
    ]

    assert sorted(bottom) == ["Drawdown", "Monthly returns", "Trades"]
    assert surface.tabifiedDockWidgets(view.dock_of(view.bottom_widget))
    view.deleteLater()


def test_the_drawdown_and_returns_docks_follow_the_run(qapp) -> None:
    """`BOT-106D` — the docks read `run_result.drawdownPoints` and
    `.yearlyReturns` reactively."""
    vm = BackTestViewModel()
    view = BackTestView()
    view.set_view_model(vm)

    vm.run_result.set_drawdown_points([{"t": 0.0, "v": -5.0}])
    qapp.processEvents()
    assert view.drawdown._plot_widget.isVisibleTo(view.drawdown)
    assert not view.drawdown._empty_label.isVisibleTo(view.drawdown)

    rows = [
        {"year": 2024, "months": [None] * 12, "ytdText": "+0.00%", "ytdColor": "#000"}
    ]
    vm.run_result.set_yearly_returns(rows)
    qapp.processEvents()
    assert view.monthly_returns._grid_container.isVisibleTo(view.monthly_returns)
    view.deleteLater()


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


def _panel_with_trades(count: int) -> BackTestTradeLogsPanel:
    vm = BackTestViewModel()
    panel = BackTestTradeLogsPanel(vm)
    vm.trade_log.set_rows([_trade_row(index) for index in range(1, count + 1)])
    return panel


def _trade_row(index: int) -> TradeLogRow:
    moment = datetime(2026, 1, 1, tzinfo=UTC)
    return TradeLogRow(
        index=index,
        entry_time=moment,
        entry_price=100.0,
        exit_time=moment,
        exit_price=101.0,
        quantity=1.0,
        pnl=1.0,
        pnl_percent=1.0,
    )


def test_selecting_a_trade_emits_its_stable_index(qapp) -> None:
    """`PROP-001` — selecting a row selects that trade for the chart's
    entry-exit link, by its index in the unfiltered list."""
    panel = _panel_with_trades(3)
    spy = MagicMock()
    panel.selectedTradeChanged.connect(spy)

    panel.table.view.selectRow(2)

    spy.assert_called_with(3)


def test_clearing_the_selection_emits_deselection(qapp) -> None:
    panel = _panel_with_trades(3)
    panel.table.view.selectRow(2)
    spy = MagicMock()
    panel.selectedTradeChanged.connect(spy)

    panel.table.view.clearSelection()

    spy.assert_called_with(-1)


def test_selecting_a_different_trade_selects_that_one(qapp) -> None:
    panel = _panel_with_trades(3)
    panel.table.view.selectRow(0)
    spy = MagicMock()
    panel.selectedTradeChanged.connect(spy)

    panel.table.view.selectRow(1)

    spy.assert_called_with(2)


def test_the_selected_trade_stays_selected_when_the_rows_are_replaced(qapp) -> None:
    """Review of PR #356: every query (a filter, a search keystroke, a time
    zone change) replaces the rows, which reset the selection and dropped
    the trade's chart line and journal. The trade stays selected while it
    still matches, and is announced once."""
    vm = BackTestViewModel()
    panel = BackTestTradeLogsPanel(vm)
    vm.trade_log.set_rows([_trade_row(index) for index in (1, 2, 3)])
    panel.table.view.selectRow(1)
    spy = MagicMock()
    panel.selectedTradeChanged.connect(spy)

    vm.trade_log.set_rows([_trade_row(index) for index in (2, 3)])

    assert panel.selected_trade is not None
    assert panel.selected_trade.index == 2
    spy.assert_called_once_with(2)


def test_a_selected_trade_the_query_no_longer_matches_is_deselected(qapp) -> None:
    vm = BackTestViewModel()
    panel = BackTestTradeLogsPanel(vm)
    vm.trade_log.set_rows([_trade_row(index) for index in (1, 2)])
    panel.table.view.selectRow(0)
    spy = MagicMock()
    panel.selectedTradeChanged.connect(spy)

    vm.trade_log.set_rows([_trade_row(2)])

    assert panel.selected_trade is None
    spy.assert_called_once_with(-1)
