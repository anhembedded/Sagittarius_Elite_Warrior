"""
Tests for BaseStrategy's parameter-declaration mechanism (BOT-046) — the same
`input_*()`/`inputs` API `BaseIndicatorScript` got in BOT-044, reused here via
`domain/scripting/` rather than shared through inheritance (the two base
classes stay deliberately separate, see BaseStrategy's docstring).

The value/validation semantics (defaults, min/max, options, "raise on an
undeclared param") are already covered exhaustively for the shared
`InputDeclarations`/`ScriptInput` machinery in
`tests/unit/domain/scripting/test_inputs.py` — these tests only prove
BaseStrategy wires that machinery correctly: setup() runs before
build_indicators()/decide() ever see a resolved value, and `params` flows
through unchanged.
"""

import pytest

from Sagittarius_Elite_Warrior.src.domain.indicators.i_indicator import IIndicator
from Sagittarius_Elite_Warrior.src.domain.strategies.base_strategy import BaseStrategy
from Sagittarius_Elite_Warrior.src.domain.strategies.strategy_context import (
    IndicatorValue,
    StrategyContext,
)


class _ParameterisedStrategy(BaseStrategy):
    """Declares a parameter and uses it to build its (fake) indicator set —
    the same shape a real strategy like EmaCrossoverStrategy has."""

    KEY = "value"

    def setup(self) -> None:
        self.period = self.input_int(
            "period", 20, label="Period", minval=1, maxval=200, group="Tuning"
        )

    def build_indicators(self) -> dict[str, IIndicator[IndicatorValue]]:
        # Not a real IIndicator — this strategy is only ever used to prove
        # `self.period` already holds the resolved value by the time
        # build_indicators() runs, never to be fed through a real engine.
        return {self.KEY: self.period}  # type: ignore[dict-item]

    def decide(self, context: StrategyContext):
        return self.hold()


class _NoParamsStrategy(BaseStrategy):
    """A strategy written the pre-BOT-046 way — declares nothing."""

    def build_indicators(self) -> dict[str, IIndicator[IndicatorValue]]:
        return {}

    def decide(self, context: StrategyContext):
        return self.hold()


def test_a_strategy_declaring_no_params_has_an_empty_schema():
    """Every strategy written before BOT-046 falls in this case — the whole
    point is that they keep working untouched."""
    assert _NoParamsStrategy().inputs == ()


def test_schema_carries_everything_a_form_needs():
    (spec,) = _ParameterisedStrategy().inputs

    assert spec.name == "period"
    assert spec.label == "Period"
    assert spec.default == 20
    assert (spec.minval, spec.maxval, spec.group) == (1, 200, "Tuning")


def test_no_params_uses_the_declared_default():
    assert _ParameterisedStrategy().period == 20


def test_supplied_params_override_the_default():
    assert _ParameterisedStrategy({"period": 50}).period == 50


def test_build_indicators_sees_the_resolved_value_not_the_default():
    """The ordering guarantee this task exists for: setup() runs — and
    resolves every input — before build_indicators() is ever called."""
    strategy = _ParameterisedStrategy({"period": 7})

    assert strategy.build_indicators() == {_ParameterisedStrategy.KEY: 7}


def test_an_undeclared_param_raises():
    with pytest.raises(ValueError, match="never declares"):
        _ParameterisedStrategy({"perod": 50})


def test_an_out_of_range_value_raises_rather_than_being_clamped():
    with pytest.raises(ValueError, match="must be <= 200"):
        _ParameterisedStrategy({"period": 500})


def test_ema_crossover_strategy_declares_its_periods():
    """The real strategy this task converts — proves the conversion actually
    happened, not just the test double above."""
    from Sagittarius_Elite_Warrior.src.domain.strategies.ema_crossover_strategy import (
        EmaCrossoverStrategy,
    )

    names = {spec.name for spec in EmaCrossoverStrategy().inputs}

    assert names == {"fast_period", "slow_period"}


def test_ema_crossover_strategy_default_periods_are_unchanged():
    """Pins BOT-046's stated constraint: converting to input_int() must not
    move the defaults away from 12/26."""
    from Sagittarius_Elite_Warrior.src.domain.strategies.ema_crossover_strategy import (
        EmaCrossoverStrategy,
    )

    defaults = {spec.name: spec.default for spec in EmaCrossoverStrategy().inputs}

    assert defaults == {"fast_period": 12, "slow_period": 26}
