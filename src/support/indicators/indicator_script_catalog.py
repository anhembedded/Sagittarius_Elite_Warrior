"""`BOT-063` — an indicator script's params form, the same shape
`IStrategyCatalog` publishes for a strategy's.

@details No interface/Protocol, mirroring `IndicatorScriptRegistry`'s own
reasoning (that class's docstring): exactly one implementation, one
consumer tree (the Dev Board's per-script params dialog), nothing to
swap. Delegates the schema-fold and the coerce-and-validate step to
`param_form.py` so this stays the same two thin methods
`StrategyCatalogService` has, never a second copy of either.
"""

from __future__ import annotations

from collections.abc import Mapping

from Sagittarius_Elite_Warrior.src.core.contracts.param_field import ParamGroup
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_script_registry import (
    IndicatorScriptRegistry,
)
from Sagittarius_Elite_Warrior.src.support.indicators.scripting.param_form import (
    ParamValidation,
    build_param_groups,
    validate_params,
)


class IndicatorScriptCatalog:
    """Every registered indicator script's declared parameters."""

    def __init__(self, registry: IndicatorScriptRegistry) -> None:
        self._registry = registry

    def params_form(
        self, key: str, values: Mapping[str, object]
    ) -> tuple[ParamGroup, ...]:
        """@raises KeyError for an unregistered `key` (`registry.create()`'s
        own contract)."""
        schema = self._registry.create(key).inputs
        return build_param_groups(schema, values)

    def validate_params(self, key: str, raw: Mapping[str, object]) -> ParamValidation:
        schema = self._registry.create(key).inputs
        return validate_params(
            schema, raw, lambda parsed: self._registry.create(key, parsed)
        )
