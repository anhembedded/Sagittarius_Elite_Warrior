"""`ParamValidation` — the result of checking a strategy's raw parameter
input against its own declared schema.

@details `IStrategyCatalog.validate_params()`'s return type. Deliberately
one type with an empty-string-means-accepted `error`, matching
`ArmStrategyResult`'s own shape (a named outcome, never a bare `bool` with
the reason left for the caller to guess) — `parse_bot_params()` used to
raise `ValueError` across the call, which is not a UI-branchable answer
once the call crosses a module boundary through `ICommandDispatcher`
instead of a plain Python function call.
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
