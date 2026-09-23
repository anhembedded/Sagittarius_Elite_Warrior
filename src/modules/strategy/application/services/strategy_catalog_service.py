"""`StrategyCatalogService` — `IStrategyCatalog`'s implementation.

@details Everything `bot_params_form.py` used to do for a caller outside
this module, now done here instead of exported: the throwaway-instance
build, the `.inputs` read. Callers get `core/contracts`' `ParamGroup`/
`ParamField`, not the QML-era `list[dict]` shape (`code/quality.md` §1
forbids the loose dict crossing at all).

The schema-to-form fold and the coerce-and-construct-and-discard
validation step live in `support/indicators/scripting/param_form.py`
(`BOT-063`) —
shared with `IndicatorScriptCatalog`, since `BaseStrategy`/
`BaseIndicatorScript` both publish the identical `ScriptInput` shape.
This service's own `ParamValidation` stays module-owned (`contracts/
param_validation.py`) rather than importing the shared helper's copy —
see that helper's own docstring for why.
"""

from __future__ import annotations

from collections.abc import Mapping

from Sagittarius_Elite_Warrior.src.core.contracts.param_field import ParamGroup
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_strategy_catalog import (
    IStrategyCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.param_validation import (
    ParamValidation,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.strategy_option import (
    StrategyOption,
)
from Sagittarius_Elite_Warrior.src.support.indicators.scripting.param_form import (
    build_param_groups,
    validate_params,
)


class StrategyCatalogService(IStrategyCatalog):
    def __init__(self, registry: StrategyRegistry) -> None:
        self._registry = registry

    def options(self) -> tuple[StrategyOption, ...]:
        return tuple(
            StrategyOption(key=key, label=_humanize(key))
            for key in sorted(self._registry.available())
        )

    def params_form(
        self, key: str, values: Mapping[str, object]
    ) -> tuple[ParamGroup, ...]:
        schema = self._require(key)().inputs
        return build_param_groups(schema, values)

    def validate_params(self, key: str, raw: Mapping[str, object]) -> ParamValidation:
        strategy_cls = self._require(key)
        result = validate_params(strategy_cls().inputs, raw, strategy_cls)
        return ParamValidation(values=result.values, error=result.error)

    def _require(self, key: str) -> type:
        strategy_cls = self._registry.available().get(key)
        if strategy_cls is None:
            raise KeyError(f"No strategy registered under key {key!r}")
        return strategy_cls


def _humanize(key: str) -> str:
    """`ema_crossover` -> `Ema Crossover`. Inlined rather than imported from
    `ui/strategy_display.py`: that function existed to stop two *screens*
    duplicating it, not for an application service to reach into `ui/`."""
    return key.replace("_", " ").title()
