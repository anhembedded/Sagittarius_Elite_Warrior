"""
@brief System Health diagnostics logging on the Backtest screen.

@details
Proves that `BackTestPresenter` asks for a fresh health reading when it is
built (`HealthCheckRequested`, `EPIC-008G`) instead of running
`HealthCheckQuery` itself, and logs each `HealthUpdatedEvent` through
`HealthStatusReport.to_log_line()`, every component included. The Dev Board
proved the same through its own `HealthCheckCoordinator` until `EPIC-033P`
deleted it; Backtest is the screen that still asks.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import MagicMock

import pytest
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.backtest_chart_host import (
    BacktestChartHostFactory,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.adapters.armed_strategy_reader_adapter import (
    ArmedStrategyReaderAdapter,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.adapters.strategy_arming_control_adapter import (
    StrategyArmingControlAdapter,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.adapters.strategy_catalog_reader_adapter import (
    StrategyCatalogReaderAdapter,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.live_strategy_factory import (
    LiveStrategyFactory,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.live_strategy_session import (
    LiveStrategySession,
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
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_armed_strategy import (
    IArmedStrategy,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_strategy_arming import (
    IStrategyArming,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_strategy_catalog import (
    IStrategyCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_strategy_chart_overlay import (
    IStrategyChartOverlay,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.testing import (
    FakeStrategyArming,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.domain.strategies.ema_crossover_strategy import (
    EmaCrossoverStrategy,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_snapshot import (
    IAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_armed_strategy_reader import (
    IArmedStrategyReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_equity_curve import (
    IEquityCurve,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_strategy_arming_control import (
    IStrategyArmingControl,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_strategy_catalog_reader import (
    IStrategyCatalogReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_snapshot import (
    FakeAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_equity_curve import (
    FakeEquityCurve,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_script_registry import (
    IndicatorScriptRegistry,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_scripts import (
    EmaCrossScript,
    EmaRibbonScript,
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

    # `EPIC-023C` — must be real, not `MagicMock()`: `StrategyArmingCoordinator`
    # reads `strategy_session.armed().config` and formats it into the card's summary,
    # and `restore_into_view_model()` calls `sorted(available_strategies())`
    strategy_registry = StrategyRegistry()
    strategy_registry.register("ema_crossover", EmaCrossoverStrategy)
    strategy_session = LiveStrategySession(
        LiveStrategyFactory(
            strategy_registry,
            MagicMock(),
            MagicMock(),
            MagicMock(),
            MagicMock(),
            MagicMock(),
            venue=TradingVenue.FUTURES_TESTNET,
        )
    )

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
        if interface == StrategyRegistry:
            return strategy_registry
        if interface in (LiveStrategySession, IArmedStrategy):
            return strategy_session
        if interface == IStrategyCatalog:
            return StrategyCatalogService(strategy_registry)
        if interface == IStrategyChartOverlay:
            return StrategyChartOverlayService(strategy_registry)
        if interface == IStrategyArming:
            return FakeStrategyArming()
        if interface == IArmedStrategyReader:
            return ArmedStrategyReaderAdapter(strategy_session)
        if interface == IStrategyCatalogReader:
            return StrategyCatalogReaderAdapter(
                StrategyCatalogService(strategy_registry)
            )
        if interface == IStrategyArmingControl:
            return StrategyArmingControlAdapter(FakeStrategyArming())
        if interface == IAccountSnapshot:
            return FakeAccountSnapshot()
        if interface == IEquityCurve:
            return FakeEquityCurve()
        if interface == HealthCheckQuery:
            return mock_health_query
        if interface == BacktestChartHostFactory:
            return BacktestChartHostFactory()
        return MagicMock()

    container.resolve.side_effect = resolve_side_effect
    return container, mock_health_query, mock_event_bus


def test_backtest_initializes_and_handles_health_updated_event(
    qapp, health_mock_container
):
    """Verify BackTestPresenter initializes and handles health events directly into log."""
    from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_presenter import (
        BackTestPresenter,
    )
    from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_view import (
        BackTestView,
    )
    from Sagittarius_Elite_Warrior.src.modules.strategy.domain.strategies.base_strategy import (
        BaseStrategy,
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

    container, mock_health_query, mock_event_bus = health_mock_container
    orig_side_effect = container.resolve.side_effect

    def resolve_with_strategy(interface):
        if interface == StrategyRegistry:
            return strategy_registry
        if interface == IStrategyCatalog:
            return StrategyCatalogService(strategy_registry)
        if interface == IStrategyChartOverlay:
            return StrategyChartOverlayService(strategy_registry)
        return orig_side_effect(interface)

    container.resolve.side_effect = resolve_with_strategy

    view = BackTestView()
    presenter = BackTestPresenter(view, container)

    # Opening the screen asks; it no longer runs the query itself.
    assert mock_health_query.execute.call_count == 0
    published = [
        call.args[0] for call in mock_event_bus.emit.call_args_list if call.args
    ]
    assert any(isinstance(event, HealthCheckRequested) for event in published), (
        "opening the screen must publish HealthCheckRequested"
    )
    presenter._health_check_coordinator._health_feed._on_health_updated(
        HealthUpdatedEvent(
            {"status": "healthy", "components": {"database": "ok", "event_bus": "ok"}}
        )
    )
    log_texts = [entry.message for entry in presenter._view_model.log_model.entries]
    assert any("[Health] System status: HEALTHY" in log for log in log_texts)

    # Re-homed from the Dev Board's health test (`EPIC-033P`): every screen
    # logs through `HealthStatusReport.to_log_line()`, so nothing is
    # hand-picked — a degraded database is named with its state, and the
    # container survives too.
    presenter._health_check_coordinator._health_feed._on_health_updated(
        HealthUpdatedEvent(
            {
                "status": "degraded",
                "components": {
                    "container": "ok",
                    "event_bus": "ok",
                    "database": "connection failed",
                },
            }
        )
    )
    latest = presenter._view_model.log_model.entries[-1].message
    assert "System status: DEGRADED" in latest
    assert "Database: CONNECTION FAILED" in latest
    assert "Container: OK" in latest
