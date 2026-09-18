"""`StrategyCatalogReaderAdapter` — implements trading's
`IStrategyCatalogReader` by wrapping `strategy`'s own, unchanged
`IStrategyCatalog`.

@details `DECISION_2026-09-17_strategy_ui_contributes_rather_than_being_imported.md`
§8. Bound in `StrategyModule.register()` (`composition/port_bindings.py`).
`ParamGroup` is already the neutral, `core`-owned type both sides use, so
`params_form()` passes it straight through — only `StrategyOption` and
`ParamValidation` need field-for-field translation into trading's own
mirrors.
"""

from __future__ import annotations

from collections.abc import Mapping

from Sagittarius_Elite_Warrior.src.core.contracts.param_field import ParamGroup
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_strategy_catalog import (
    IStrategyCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_strategy_catalog_reader import (
    IStrategyCatalogReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.strategy_option import (
    StrategyOption as TradingStrategyOption,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.strategy_param_validation import (
    ParamValidation as TradingParamValidation,
)


class StrategyCatalogReaderAdapter(IStrategyCatalogReader):
    """Translates `strategy`'s catalog answers into trading's own DTOs."""

    def __init__(self, catalog: IStrategyCatalog) -> None:
        self._catalog = catalog

    def options(self) -> tuple[TradingStrategyOption, ...]:
        return tuple(
            TradingStrategyOption(key=option.key, label=option.label)
            for option in self._catalog.options()
        )

    def params_form(
        self, key: str, values: Mapping[str, object]
    ) -> tuple[ParamGroup, ...]:
        return self._catalog.params_form(key, values)

    def validate_params(
        self, key: str, raw: Mapping[str, object]
    ) -> TradingParamValidation:
        result = self._catalog.validate_params(key, raw)
        return TradingParamValidation(values=result.values, error=result.error)
