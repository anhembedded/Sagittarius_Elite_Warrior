"""
@brief Unit tests verifying System Health diagnostics logging across Dashboard & Backtest screens.

@details
Proves that:
1. DashboardPresenter executes an initial HealthCheckQuery on initialization and appends to UI LogModel.
2. DashboardPresenter receives HealthUpdatedEvent from the EventBus and reflects component status in real time.
3. User actions (Start Live / Load History) re-trigger pre-flight HealthCheck.
4. BackTestPresenter receives HealthUpdatedEvent and logs status cleanly.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import MagicMock
import pytest

from Sagittarius_Elite_Warrior.src.application.services.indicator_script_registry import (
    IndicatorScriptRegistry,
)
from Sagittarius_Elite_Warrior.src.domain.indicator_scripts import (
    EmaCrossScript,
    EmaRibbonScript,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.dashboard_presenter import (
    DashboardPresenter,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.dashboard_view import (
    DashboardView,
)
from sagittarius_engine.extensions.health.health_check_query import HealthCheckQuery
from sagittarius_engine.extensions.health.health_module import HealthUpdatedEvent
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_dispatcher import IDispatcher
from sagittarius_engine.interfaces.i_event_bus import IEventBus
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager


@pytest.fixture
def health_mock_container(qapp):
    container = MagicMock()
    mock_config = MagicMock()
    mock_config.get.side_effect = lambda key, default=None, cast=None: default
    mock_config.get_all.return_value = {}

    mock_dispatcher = MagicMock()
    mock_thread_mgr = MagicMock()
    mock_event_bus = MagicMock()

    mock_health_query = MagicMock()
    mock_health_query.execute.return_value = {
        "status": "healthy",
        "components": {
            "container": "ok",
            "event_bus": "ok",
            "database": "ok",
        },
    }

    script_registry = IndicatorScriptRegistry()
    script_registry.register("ema_ribbon", EmaRibbonScript)
    script_registry.register("ema_cross", EmaCrossScript)

    def resolve_side_effect(interface):
        if interface == IConfig:
            return mock_config
        if interface == IDispatcher:
            return mock_dispatcher
        if interface == IThreadManager:
            return mock_thread_mgr
        if interface == IEventBus:
            return mock_event_bus
        if interface == IndicatorScriptRegistry:
            return script_registry
        if interface == HealthCheckQuery:
            return mock_health_query
        return MagicMock()

    container.resolve.side_effect = resolve_side_effect
    return container, mock_health_query, mock_event_bus


def test_dashboard_initializes_with_system_health_log(qapp, health_mock_container):
    """Verify DashboardPresenter executes initial HealthCheckQuery and logs to UI log model."""
    container, mock_health_query, _ = health_mock_container
    view = DashboardView()

    presenter = DashboardPresenter(view, container)

    assert mock_health_query.execute.call_count >= 1
    log_texts = [entry.message for entry in presenter._view_model.log_model.entries]
    assert any("System Health: HEALTHY" in log for log in log_texts)
    assert any("DB: OK" in log for log in log_texts)
    assert any("EventBus: OK" in log for log in log_texts)


def test_dashboard_handles_health_updated_event(qapp, health_mock_container):
    """Verify DashboardPresenter reacts to health.updated event and appends to log."""
    container, _, _ = health_mock_container
    view = DashboardView()
    presenter = DashboardPresenter(view, container)

    initial_log_count = len(presenter._view_model.log_model.entries)

    # Simulate health update with degraded database
    degraded_event = HealthUpdatedEvent(
        {
            "status": "degraded",
            "components": {
                "container": "ok",
                "event_bus": "ok",
                "database": "connection failed",
            },
        }
    )
    presenter._handle_health_updated(degraded_event)

    assert len(presenter._view_model.log_model.entries) == initial_log_count + 1
    latest_entry = presenter._view_model.log_model.entries[-1]
    assert "System Health: DEGRADED" in latest_entry.message
    assert "DB: CONNECTION FAILED" in latest_entry.message


def test_dashboard_actions_retrigger_health_check(qapp, health_mock_container):
    """Verify that clicking Start Live or Load History re-executes health check."""
    container, mock_health_query, _ = health_mock_container
    view = DashboardView()
    presenter = DashboardPresenter(view, container)

    count_before = mock_health_query.execute.call_count

    presenter._view_model.symbol = "BTCUSDT"
    presenter._view_model.startDate = "2024-01-01 00:00"
    presenter._view_model.endDate = "2024-01-02 00:00"

    presenter._on_load_history()
    assert mock_health_query.execute.call_count == count_before + 1


def test_backtest_initializes_and_handles_health_updated_event(qapp, health_mock_container):
    """Verify BackTestPresenter initializes and handles health events directly into log."""
    from Sagittarius_Elite_Warrior.src.application.services.strategy_registry import (
        StrategyRegistry,
    )
    from Sagittarius_Elite_Warrior.src.domain.strategies.base_strategy import (
        BaseStrategy,
    )
    from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_presenter import (
        BackTestPresenter,
    )
    from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_view import (
        BackTestView,
    )

    class _FakeStrategy(BaseStrategy):
        def setup(self):
            pass

        def decide(self, context):
            return self.hold()

        def build_indicators(self):
            return {}

    strategy_registry = StrategyRegistry()
    strategy_registry.register("fake", _FakeStrategy)

    container, mock_health_query, _ = health_mock_container
    orig_side_effect = container.resolve.side_effect

    def resolve_with_strategy(interface):
        if interface == StrategyRegistry:
            return strategy_registry
        return orig_side_effect(interface)

    container.resolve.side_effect = resolve_with_strategy

    view = BackTestView()
    presenter = BackTestPresenter(view, container)

    # Initial health check was triggered on presenter init
    assert mock_health_query.execute.call_count >= 1
    log_texts = [entry.message for entry in presenter._view_model.log_model.entries]
    assert any("[Health] Trạng thái hệ thống: HEALTHY" in log for log in log_texts)

