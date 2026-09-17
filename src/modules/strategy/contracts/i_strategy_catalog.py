"""`IStrategyCatalog` — which strategies exist, and how to edit one's
parameters, without a caller ever holding `BaseStrategy` (`EPIC-025`
`DECISION_2026-09-17_strategy_ui_contributes_rather_than_being_imported.md`).

@details HLD §3.4's planned name, revived deliberately: `EPIC-025C` §5
deleted a first `IStrategyCatalog` for being keys-only, because every
consumer measured at the time also needed the strategy *classes* — and a
published contract may not carry `BaseStrategy`. This port answers the
three questions its consumers (`trading`, `dashboard`, `backtest`) were
each measured asking, in data: which strategies exist, what a chosen
strategy's parameter form looks like, and whether a user's edited values
are valid. The class-handling that used to leak across the boundary —
building a throwaway instance, reading `.inputs` — stays inside `strategy`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping

from Sagittarius_Elite_Warrior.src.core.contracts.param_field import ParamGroup
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.param_validation import (
    ParamValidation,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.strategy_option import (
    StrategyOption,
)


class IStrategyCatalog(ABC):
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
        field's current value (falling back to that field's own default).
        The schema itself never changes with `values` — only which value
        each field reports. Raises `KeyError` for an unregistered `key`."""
        ...

    @abstractmethod
    def validate_params(self, key: str, raw: Mapping[str, object]) -> ParamValidation:
        """Coerces `raw`'s text-shaped values into `key`'s declared types.
        An unrelated key in `raw` is ignored, exactly as the strategy's own
        constructor ignores an undeclared parameter. Raises `KeyError` for
        an unregistered `key`."""
        ...
