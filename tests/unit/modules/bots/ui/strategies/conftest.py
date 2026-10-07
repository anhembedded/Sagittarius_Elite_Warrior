"""The raw strategy-owned fakes `StrategyArmingCoordinator`'s tests drive."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_catalog_service import (
    StrategyCatalogService,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.testing import (
    FakeStrategyArming,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.domain.strategies.ema_crossover_strategy import (
    EmaCrossoverStrategy,
)

from .arming_coordinator_fakes import TEST_STRATEGY_KEY, FakeCardViewModel


@pytest.fixture
def strategy_registry() -> StrategyRegistry:
    registry = StrategyRegistry()
    registry.register(TEST_STRATEGY_KEY, EmaCrossoverStrategy)
    return registry


@pytest.fixture
def catalog(strategy_registry: StrategyRegistry) -> StrategyCatalogService:
    """The real, cheap service over an in-memory registry, not a `Mock`:
    `testing-rule.md` §2 prefers the real thing when it costs nothing."""
    return StrategyCatalogService(strategy_registry)


@pytest.fixture
def arming() -> FakeStrategyArming:
    return FakeStrategyArming()


@pytest.fixture
def view_model() -> FakeCardViewModel:
    return FakeCardViewModel()
