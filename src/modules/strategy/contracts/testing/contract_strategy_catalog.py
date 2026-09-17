"""The contract suite for `IStrategyCatalog` (HLD §10.3).

**No `BaseStrategy` crosses.** `options()` returns display data, not
classes; a real implementation builds the throwaway instance internally
and a test double never has to.

**An unregistered key raises, it does not return an empty form.** Silently
answering "no parameters" for a key nobody registered would read
identically to "this strategy really has none", which is the exact
untruthful shape `domain-truth-rule.md` forbids.

**Validation is one answer, not an exception.** `parse_bot_params()` used
to raise `ValueError` across a plain function call; a port crossing a
module boundary answers in data instead, so a caller never needs a
`try`/`except` around a dispatch.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_strategy_catalog import (
    IStrategyCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.strategy_option import (
    StrategyOption,
)

#: How a subclass seeds one registered strategy — the fake takes it as a
#: constructor argument, the real service needs a `StrategyRegistry` with
#: something registered on it.
type Register = Callable[[str], None]


class StrategyCatalogContract:
    """Inherit this, provide `impl` (with one strategy already registered
    under `a_key`) and `register`."""

    a_key = "ema_crossover"

    @pytest.fixture
    def impl(self) -> IStrategyCatalog:
        raise NotImplementedError(
            "a StrategyCatalogContract subclass must provide an `impl` fixture, "
            "with `a_key` already registered"
        )

    def test_options_lists_what_is_registered(self, impl: IStrategyCatalog) -> None:
        options = impl.options()

        assert StrategyOption(key=self.a_key, label="Ema Crossover") in options

    def test_params_form_of_an_unregistered_key_raises(
        self, impl: IStrategyCatalog
    ) -> None:
        with pytest.raises(KeyError):
            impl.params_form("no_such_strategy", {})

    def test_validate_params_of_an_unregistered_key_raises(
        self, impl: IStrategyCatalog
    ) -> None:
        with pytest.raises(KeyError):
            impl.validate_params("no_such_strategy", {})

    def test_params_form_returns_groups(self, impl: IStrategyCatalog) -> None:
        groups = impl.params_form(self.a_key, {})

        assert isinstance(groups, tuple)

    def test_validate_params_answers_in_data_not_an_exception(
        self, impl: IStrategyCatalog
    ) -> None:
        """Whatever the verdict, `validate_params` must return rather than
        raise — a caller across a module boundary through
        `ICommandDispatcher` has no exception to catch."""
        result = impl.validate_params(self.a_key, {})

        assert result.accepted or result.error != ""
