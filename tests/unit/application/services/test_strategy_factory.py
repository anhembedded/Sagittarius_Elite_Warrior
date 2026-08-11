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

    engine = build_engine(registry, "ema_crossover", event_bus=Mock())

    assert isinstance(engine, StrategyEngine)
    assert isinstance(engine._strategy, EmaCrossoverStrategy)
    assert set(engine._indicators.keys()) == {
        EmaCrossoverStrategy.FAST_KEY,
        EmaCrossoverStrategy.SLOW_KEY,
    }


def test_build_engine_raises_for_an_unregistered_key():
    registry = StrategyRegistry()

    with pytest.raises(KeyError):
        build_engine(registry, "nope", event_bus=Mock())
