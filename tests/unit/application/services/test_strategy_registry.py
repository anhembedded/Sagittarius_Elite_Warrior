"""Tests for StrategyRegistry (BOT-026)."""

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.application.services.strategy_engine import (
    StrategyEngine,
)
from Sagittarius_Elite_Warrior.src.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.strategies.base_strategy import BaseStrategy
from Sagittarius_Elite_Warrior.src.domain.strategies.ema_crossover_strategy import (
    EmaCrossoverStrategy,
)
from Sagittarius_Elite_Warrior.src.domain.strategies.strategy_context import (
    StrategyContext,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal_action import (
    SignalAction,
)


def _build_klines(closes: list[float]) -> list[MarketData]:
    base_time = datetime(2024, 1, 1, tzinfo=UTC)
    klines = []
    for i, close in enumerate(closes):
        open_time = base_time + timedelta(minutes=i)
        close_time = open_time + timedelta(minutes=1)
        klines.append(
            MarketData(
                symbol="BTCUSDT",
                interval="1m",
                open_time=open_time,
                open_price=close,
                high_price=close,
                low_price=close,
                close_price=close,
                volume=1000.0,
                close_time=close_time,
                quote_asset_volume=close * 1000.0,
                number_of_trades=10,
                taker_buy_base_asset_volume=500.0,
                taker_buy_quote_asset_volume=500.0 * close,
            )
        )
    return klines


class _DummyStrategy(BaseStrategy):
    def decide(self, context: StrategyContext) -> tuple[SignalAction, str]:
        return self.hold()

    def build_indicators(self) -> dict:
        return {}


class _OtherStrategy(_DummyStrategy):
    pass


class _ParameterisedStrategy(BaseStrategy):
    """Declares a parameter, so `create(key, params)` has something to reach."""

    def setup(self) -> None:
        self.period = self.input_int("period", 20, minval=1)

    def decide(self, context: StrategyContext) -> tuple[SignalAction, str]:
        return self.hold()

    def build_indicators(self) -> dict:
        return {}


@pytest.fixture
def registry() -> StrategyRegistry:
    return StrategyRegistry()


def test_register_then_create_returns_an_instance(registry):
    registry.register("dummy", _DummyStrategy)

    assert isinstance(registry.create("dummy"), _DummyStrategy)


def test_create_returns_a_fresh_instance_every_call(registry):
    registry.register("dummy", _DummyStrategy)

    assert registry.create("dummy") is not registry.create("dummy")


def test_create_passes_params_through_to_the_strategy(registry):
    """BOT-046: `params` reaches the strategy's `input_*()` declarations,
    the same way `IndicatorScriptRegistry.create()` already does (BOT-044)."""
    registry.register("parameterised", _ParameterisedStrategy)

    strategy = registry.create("parameterised", {"period": 5})

    assert strategy.period == 5


def test_create_without_params_uses_the_strategys_own_defaults(registry):
    registry.register("parameterised", _ParameterisedStrategy)

    assert registry.create("parameterised").period == 20


def test_duplicate_key_raises_instead_of_silently_overwriting(registry):
    registry.register("dummy", _DummyStrategy)

    with pytest.raises(ValueError, match="already registered"):
        registry.register("dummy", _OtherStrategy)


def test_unknown_key_raises_keyerror(registry):
    with pytest.raises(KeyError):
        registry.create("nope")


def test_available_lists_registered_strategies(registry):
    registry.register("dummy", _DummyStrategy)
    registry.register("other", _OtherStrategy)

    assert registry.available() == {"dummy": _DummyStrategy, "other": _OtherStrategy}


def test_available_returns_a_copy(registry):
    registry.register("dummy", _DummyStrategy)

    registry.available()["injected"] = _OtherStrategy

    assert "injected" not in registry.available()


def test_create_returns_an_independent_strategy_instance_per_call(registry):
    """A strategy tracks cross-detection state in its own `Series` — proves
    that state doesn't leak between two instances created from the same key,
    the same failure mode `IndicatorScriptRegistry.create()` already guards
    against (no `reset()`, so a fresh run needs a genuinely fresh object)."""
    registry.register("ema_crossover", EmaCrossoverStrategy)
    strategy_a = registry.create("ema_crossover")
    engine_a = StrategyEngine(
        indicators=strategy_a.build_indicators(),
        strategy=strategy_a,
        event_bus=Mock(),
    )
    # 30 rising closes is enough to clear EmaCrossoverStrategy's default
    # warm-up (slow EMA period 26) and push at least one real value into
    # strategy_a's internal Series.
    klines = _build_klines([100.0 + i for i in range(30)])
    engine_a.run_batch(klines)
    assert strategy_a.series(EmaCrossoverStrategy.FAST_KEY).current is not None

    strategy_b = registry.create("ema_crossover")

    assert strategy_b.series(EmaCrossoverStrategy.FAST_KEY).current is None
    assert strategy_b.series(EmaCrossoverStrategy.FAST_KEY) is not strategy_a.series(
        EmaCrossoverStrategy.FAST_KEY
    )
