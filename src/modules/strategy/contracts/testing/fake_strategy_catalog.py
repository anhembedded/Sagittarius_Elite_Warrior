"""`FakeStrategyCatalog` — `IStrategyCatalog`'s verified fake.

A test says what strategies exist and what their forms look like; nothing
here reads `BaseStrategy` or builds an instance — a consumer's test that
needed the real registry would be testing the registry, not the screen.
"""

from __future__ import annotations

from collections.abc import Mapping

from Sagittarius_Elite_Warrior.src.core.contracts.param_field import ParamGroup
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_strategy_catalog import (
    IStrategyCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.param_validation import (
    ParamValidation,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.strategy_option import (
    StrategyOption,
)


class FakeStrategyCatalog(IStrategyCatalog):
    """Scripted answers: seed `options` and each key's `forms` entry; a
    test controls `validate_params`'s answer with `script_validation()`."""

    def __init__(
        self,
        options: tuple[StrategyOption, ...] = (),
        forms: Mapping[str, tuple[ParamGroup, ...]] | None = None,
    ) -> None:
        self._options = options
        self._forms = dict(forms or {})
        self._scripted_validation: ParamValidation | None = None
        #: How many times each method was read, for the same reason
        #: `FakeArmedStrategy` counts reads.
        self.options_reads = 0
        self.params_form_reads = 0
        self.validate_params_reads = 0

    def script_validation(self, result: ParamValidation) -> None:
        """The next `validate_params()` call answers with `result` instead
        of the default accept-everything behaviour."""
        self._scripted_validation = result

    def options(self) -> tuple[StrategyOption, ...]:
        self.options_reads += 1
        return self._options

    def params_form(
        self, key: str, values: Mapping[str, object]
    ) -> tuple[ParamGroup, ...]:
        self.params_form_reads += 1
        if key not in self._forms:
            raise KeyError(f"No strategy registered under key {key!r}")
        return self._forms[key]

    def validate_params(self, key: str, raw: Mapping[str, object]) -> ParamValidation:
        self.validate_params_reads += 1
        if key not in self._forms:
            raise KeyError(f"No strategy registered under key {key!r}")
        if self._scripted_validation is not None:
            return self._scripted_validation
        return ParamValidation(values=dict(raw))
