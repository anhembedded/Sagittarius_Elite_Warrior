"""`IStrategyCatalogReader` — trading's own view of which strategies exist
and how to edit one's parameters, without naming the module that owns
`BaseStrategy`.

@details `DECISION_2026-09-17_strategy_ui_contributes_rather_than_being_imported.md`
§8 — see `i_armed_strategy_reader.py` in this package for the full boot-order
reasoning. `ParamGroup` stays the neutral, `core`-owned type it already was
(`EPIC-025` PR 4.3m); only the strategy-owned `StrategyOption`/`ParamValidation`
shapes need trading-owned mirrors.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping

from Sagittarius_Elite_Warrior.src.core.contracts.param_field import ParamGroup
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.strategy_option import (
    StrategyOption,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.strategy_param_validation import (
    ParamValidation,
)


class IStrategyCatalogReader(ABC):
    """Every registered strategy, and its parameter form."""

    @abstractmethod
    def options(self) -> tuple[StrategyOption, ...]:
        """Every registered strategy, key plus display label."""
        ...

    @abstractmethod
    def params_form(
        self, key: str, values: Mapping[str, object]
    ) -> tuple[ParamGroup, ...]:
        """`key`'s declared parameters, grouped, with `values` shown as each
        field's current value. Raises `KeyError` for an unregistered `key`."""
        ...

    @abstractmethod
    def validate_params(self, key: str, raw: Mapping[str, object]) -> ParamValidation:
        """Coerces `raw`'s text-shaped values into `key`'s declared types.
        Raises `KeyError` for an unregistered `key`."""
        ...
