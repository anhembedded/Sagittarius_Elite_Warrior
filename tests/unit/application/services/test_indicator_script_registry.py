"""Tests for IndicatorScriptRegistry (BOT-032 Phase 0)."""

import pytest
from Sagittarius_Elite_Warrior.src.application.services.indicator_script_registry import (
    IndicatorScriptRegistry,
)
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.indicator_scripts import BaseIndicatorScript


class _DummyScript(BaseIndicatorScript):
    title = "Dummy"
    overlay = True

    def setup(self) -> None:
        self.e = self.ema(2)

    def execute(self, candle: MarketData) -> None:
        self.plot(self.e(candle.close_price), "LINE", color="#ffffff")


class _OtherScript(_DummyScript):
    title = "Other"


class _ParameterisedScript(BaseIndicatorScript):
    """Declares a parameter, so `create(key, params)` has something to reach."""

    title = "Parameterised"
    overlay = True

    def setup(self) -> None:
        self.period = self.input_int("period", 2, minval=1)
        self.e = self.ema(self.period)

    def execute(self, candle: MarketData) -> None:
        self.plot(self.e(candle.close_price), "LINE", color="#ffffff")


@pytest.fixture
def registry() -> IndicatorScriptRegistry:
    return IndicatorScriptRegistry()


def test_register_then_create_returns_an_instance(registry):
    registry.register("dummy", _DummyScript)

    assert isinstance(registry.create("dummy"), _DummyScript)


def test_create_returns_a_fresh_instance_every_call(registry):
    """Indicators carry warm-up state and have no reset(), so each run must
    start from a brand new object."""
    registry.register("dummy", _DummyScript)

    assert registry.create("dummy") is not registry.create("dummy")


def test_duplicate_key_raises_instead_of_silently_overwriting(registry):
    registry.register("dummy", _DummyScript)

    with pytest.raises(ValueError, match="already registered"):
        registry.register("dummy", _OtherScript)


def test_unknown_key_raises_keyerror(registry):
    with pytest.raises(KeyError):
        registry.create("nope")


def test_create_passes_params_through_to_the_script(registry):
    """BOT-044 turned the reserved `params` argument into a real one: it now
    reaches the script's `input_*()` declarations. Before that it was
    accepted and ignored, which is why this test changed shape rather than
    being a regression."""
    registry.register("parameterised", _ParameterisedScript)

    script = registry.create("parameterised", {"period": 5})

    assert script.period == 5


def test_create_without_params_uses_the_scripts_own_defaults(registry):
    registry.register("parameterised", _ParameterisedScript)

    assert registry.create("parameterised").period == 2


def test_create_rejects_a_param_the_script_never_declares(registry):
    """Silently ignoring it would leave the caller believing a setting took
    effect — see BaseIndicatorScript.__init__."""
    registry.register("dummy", _DummyScript)

    with pytest.raises(ValueError, match="never declares"):
        registry.create("dummy", {"period": 20})


def test_available_lists_registered_scripts(registry):
    registry.register("dummy", _DummyScript)
    registry.register("other", _OtherScript)

    assert registry.available() == {"dummy": _DummyScript, "other": _OtherScript}


def test_available_returns_a_copy(registry):
    registry.register("dummy", _DummyScript)

    registry.available()["injected"] = _OtherScript

    assert "injected" not in registry.available()
