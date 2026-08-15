from __future__ import annotations

from unittest.mock import MagicMock

from PySide6.QtCore import QUrl
from PySide6.QtQuick import QQuickItem
from Sagittarius_Elite_Warrior.src.domain.events.backtest_completed_event import (
    BacktestCompletedEvent,
)
from Sagittarius_Elite_Warrior.src.domain.events.backtest_failed_event import (
    BacktestFailedEvent,
)
from Sagittarius_Elite_Warrior.src.domain.events.signal_generated_event import (
    SignalGeneratedEvent,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_view import (
    _QML_DIR,
    _TRADE_LOGS_QML,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_view_model import (
    BackTestViewModel,
)
from sagittarius_engine.extensions.pyside_mvc import create_quick_widget

_QML_FILE = _QML_DIR / _TRADE_LOGS_QML


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


def test_backtest_bottom_tabs_qml_parses_and_renders(qapp, qtbot) -> None:
    vm = BackTestViewModel()
    widget = create_quick_widget()
    widget.rootContext().setContextProperty("viewModel", vm)
    widget.setSource(QUrl.fromLocalFile(str(_QML_FILE)))

    assert widget.errors() == []
    root = widget.rootObject()
    assert root is not None

    # Check that bottomTabBar exists
    tab_bar = root.findChild(QQuickItem, "bottomTabBar")
    assert tab_bar is not None

    # Check tab 1 (trade logs tab content) is visible initially
    trade_logs_content = root.findChild(QQuickItem, "tradeLogsTabContent")
    assert trade_logs_content is not None
    assert trade_logs_content.isVisible()

    # Check log panel is hidden initially
    log_panel = root.findChild(QQuickItem, "backtestLogPanel")
    assert log_panel is not None
    assert not log_panel.isVisible()

    # Switch to logs tab
    vm.setActiveBottomTab("logs")
    qtbot.waitUntil(lambda: log_panel.isVisible(), timeout=1000)
    assert not trade_logs_content.isVisible()
    assert log_panel.isVisible()

    # Switch back to trades tab
    vm.setActiveBottomTab("trades")
    qtbot.waitUntil(lambda: trade_logs_content.isVisible(), timeout=1000)
    assert trade_logs_content.isVisible()
    assert not log_panel.isVisible()


def test_backtest_presenter_event_bus_handlers(qapp) -> None:
    from Sagittarius_Elite_Warrior.src.application.services.indicator_script_registry import (
        IndicatorScriptRegistry,
    )
    from Sagittarius_Elite_Warrior.src.application.services.strategy_registry import (
        StrategyRegistry,
    )
    from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_presenter import (
        BackTestPresenter,
    )
    from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_view import (
        BackTestView,
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
        if interface == IndicatorScriptRegistry:
            return script_reg
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
    presenter._view_model.selectedStrategyKey = "multi_ema_trend_follower"
    assert presenter._view_model.log_model.rowCount() == current_count + 1
    idx = presenter._view_model.log_model.index(current_count, 0)
    assert "chiến lược" in presenter._view_model.log_model.data(
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
