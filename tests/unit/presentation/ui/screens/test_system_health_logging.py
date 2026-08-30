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
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.backtest_chart_host import (
    BacktestChartHostFactory,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.dashboard_presenter import (
    DashboardPresenter,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.dashboard_view import (
    DashboardView,
)
from sagittarius_engine.extensions.health.health_check_query import HealthCheckQuery
from sagittarius_engine.extensions.health.health_check_requested import (
    HealthCheckRequested,
)
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
        if interface == BacktestChartHostFactory:
            return BacktestChartHostFactory()
        return MagicMock()

    container.resolve.side_effect = resolve_side_effect
    return container, mock_health_query, mock_event_bus


def test_dashboard_asks_for_health_instead_of_running_the_query_itself(
    qapp, health_mock_container
):
    """`EPIC-008G`: the screen no longer resolves `HealthCheckQuery` and builds
    its own `HealthUpdatedEvent`.

    That workaround existed because `HealthExtension.boot()` publishes exactly
    once, at `app.boot()`, before any lazily-built presenter exists.
    `EPIC-008E` replaced it with a real request/response pair, so the screen
    now just asks — and the answer arrives over the same event path as every
    other health update, leaving one code path instead of two."""
    container, mock_health_query, mock_event_bus = health_mock_container
    view = DashboardView()

    presenter = DashboardPresenter(view, container)

    assert mock_health_query.execute.call_count == 0, (
        "the screen must not run the health query itself any more"
    )
    published = [
        call.args[0] for call in mock_event_bus.emit.call_args_list if call.args
    ]
    assert any(isinstance(event, HealthCheckRequested) for event in published), (
        "opening the screen must publish HealthCheckRequested"
    )
    assert presenter._health_check_coordinator._health_feed is not None


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
    presenter._health_check_coordinator._health_feed._on_health_updated(degraded_event)

    assert len(presenter._view_model.log_model.entries) == initial_log_count + 1
    latest_entry = presenter._view_model.log_model.entries[-1]
    # Format changed with EPIC-008G and the user approved it: both screens now
    # render through HealthStatusReport.to_log_line(), so they can no longer
    # disagree about the same fact the way they used to.
    assert "Trạng thái hệ thống: DEGRADED" in latest_entry.message
    assert "Database: CONNECTION FAILED" in latest_entry.message
    # Backtest's own formatter used to omit `container` entirely; nothing is
    # hand-picked any more, so it survives.
    assert "Container: OK" in latest_entry.message


def test_dashboard_initial_health_check_single_log(qapp, health_mock_container):
    """Verify that clicking Start Live or Load History does not duplicate health log."""
    container, _mock_health_query, mock_event_bus = health_mock_container
    view = DashboardView()
    presenter = DashboardPresenter(view, container)

    def _requests() -> int:
        return sum(
            1
            for call in mock_event_bus.emit.call_args_list
            if call.args and isinstance(call.args[0], HealthCheckRequested)
        )

    count_before = _requests()
    assert count_before >= 1

    presenter._view_model.symbol = "BTCUSDT"
    presenter._view_model.startDate = "2024-01-01 00:00"
    presenter._view_model.endDate = "2024-01-02 00:00"

    presenter._on_load_history()
    # An ordinary user action must not re-ask for health.
    assert _requests() == count_before


def test_backtest_initializes_and_handles_health_updated_event(
    qapp, health_mock_container
):
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

    # Opening the screen asks; it no longer runs the query itself.
    assert mock_health_query.execute.call_count == 0
    presenter._health_check_coordinator._health_feed._on_health_updated(
        HealthUpdatedEvent(
            {"status": "healthy", "components": {"database": "ok", "event_bus": "ok"}}
        )
    )
    log_texts = [entry.message for entry in presenter._view_model.log_model.entries]
    assert any("[Health] Trạng thái hệ thống: HEALTHY" in log for log in log_texts)
