"""Tests for build_engine (BOT-026)."""

from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.application.services.strategy_engine import (
    StrategyEngine,
)
from Sagittarius_Elite_Warrior.src.application.services.strategy_factory import (
    build_engine,
)
from Sagittarius_Elite_Warrior.src.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.domain.strategies.ema_crossover_strategy import (
    EmaCrossoverStrategy,
)


def test_build_engine_wires_a_fresh_strategy_with_its_own_indicators():
    registry = StrategyRegistry()
    registry.register("ema_crossover", EmaCrossoverStrategy)

    engine = build_engine(registry, "ema_crossover", event_publisher=Mock())

    assert isinstance(engine, StrategyEngine)
    assert isinstance(engine._strategy, EmaCrossoverStrategy)
    assert set(engine._indicators.keys()) == {
        EmaCrossoverStrategy.FAST_KEY,
        EmaCrossoverStrategy.SLOW_KEY,
    }


def test_build_engine_raises_for_an_unregistered_key():
    registry = StrategyRegistry()

    with pytest.raises(KeyError):
        build_engine(registry, "nope", event_publisher=Mock())


def test_build_engine_passes_params_through_and_builds_indicators_from_them():
    """BOT-046: a custom period supplied through `build_engine()` must reach
    the actual `EMA` instances the engine runs — not just the strategy's own
    `self._fast_period` attribute."""
    registry = StrategyRegistry()
    registry.register("ema_crossover", EmaCrossoverStrategy)

    engine = build_engine(
        registry,
        "ema_crossover",
        event_publisher=Mock(),
        params={"fast_period": 7, "slow_period": 21},
    )

    fast = engine._indicators[EmaCrossoverStrategy.FAST_KEY]
    slow = engine._indicators[EmaCrossoverStrategy.SLOW_KEY]
    assert fast._period == 7
    assert slow._period == 21
