"""The container a Backtest screen's modal tests boot a real `BackTestPresenter`
over: real catalog, overlay, script registry, chart host and metadata cache,
and a `Mock` only for what the modals never read."""

from __future__ import annotations

from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.backtest_chart_host import (
    BacktestChartHostFactory,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.persistence.symbol_market_metadata_cache import (
    InMemorySymbolMarketMetadataCache,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_symbol_market_metadata_cache import (
    ISymbolMarketMetadataCache,
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


def backtest_screen_container(registry: StrategyRegistry) -> Mock:
    """A container resolving `registry`'s strategies for a Backtest screen."""
    container = Mock()

    def resolve(interface: object) -> object:
        if interface == IConfig:
            config = Mock()
            config.get_all.return_value = {}
            config.get.return_value = None
            return config
        if interface == StrategyRegistry:
            return registry
        if interface == IStrategyCatalog:
            return StrategyCatalogService(registry)
        if interface == IStrategyChartOverlay:
            return StrategyChartOverlayService(registry)
        if interface == IndicatorScriptRegistry:
            return IndicatorScriptRegistry()
        if interface == BacktestChartHostFactory:
            return BacktestChartHostFactory()
        # `BUG-127`: the real in-memory cache, never the `Mock()` below, whose
        # `get()` answers a truthy object with a truthy `is_stale()`.
        if interface == ISymbolMarketMetadataCache:
            return InMemorySymbolMarketMetadataCache()
        return Mock()

    container.resolve.side_effect = resolve
    return container
