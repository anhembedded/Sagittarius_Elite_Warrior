"""`ParamValidation` — trading's own copy of a parameter-validation outcome.

@details `IStrategyCatalogReader.validate_params()`'s return type; see
`armed_strategy_config.py` in this package for why trading owns a mirror
rather than importing `modules.strategy.contracts.param_validation`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ParamValidation:
    """`values` holds the coerced parameters when `error` is `""`; both are
    always present so a caller need not branch on which field is real."""

    values: Mapping[str, object] = field(default_factory=dict)
    error: str = ""

    @property
    def accepted(self) -> bool:
        return self.error == ""
