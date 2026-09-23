"""`BOT-063` — the `ScriptInput` -> `ParamGroup`/`ParamField` builder and
the raw-values -> coerced-and-validated step, shared by every consumer of
a `.inputs` declaration (`BaseStrategy` and `BaseIndicatorScript` both
expose the identical `ScriptInput` shape).

@details Pulled out of `modules/strategy/application/services/
strategy_catalog_service.py` (formerly private `_field`/`_coerce`) so
indicator scripts do not grow a second, drifting copy of the same two
functions the moment they need their own params form (`architecture-rule.md`
§3: a module imports another module only through its `contracts/`, and a
support package imports no module at all — a shared module-facing helper
has to live in a support package both `modules/strategy` and this package's
own `IndicatorScriptCatalog` can reach).

Lives inside `scripting/`, not directly under `support/indicators/`, so
`modules/strategy` (outside its own `ui/`) can import it at all: the
architecture boundary guard (`tests/unit/architecture/boundaries/rules.py`
`_COMPUTATION_SUB_PACKAGES`) only lets a non-`ui/` module reach a *named*
`support/indicators` sub-package — `indicators`/`indicator_scripts`/
`scripting`/`indicator_script_registry` — never the package's root.

`ParamValidation` here is `support/indicators`' own copy, not an import of
`modules.strategy.contracts.param_validation.ParamValidation` — mirrors the
precedent `modules/trading/contracts/strategy_param_validation.py` already
set (`DECISION_2026-09-17_strategy_ui_contributes_rather_than_being_imported.md`):
a value-only outcome type is cheap to duplicate exactly and expensive to
couple two otherwise-independent trees over. `ParamGroup`/`ParamField`
stay the one shared `core/contracts` type — they cross the same boundary
today via `IStrategyCatalog.params_form()`, so a second copy of *those*
would drift.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field

from Sagittarius_Elite_Warrior.src.core.contracts.param_field import (
    ParamField,
    ParamGroup,
    ParamKind,
)
from Sagittarius_Elite_Warrior.src.support.indicators.scripting import (
    InputKind,
    ScriptInput,
)


@dataclass(frozen=True, slots=True)
class ParamValidation:
    """`values` holds the coerced parameters when `error` is `""`; both are
    always present so a caller need not branch on which field is real."""

    values: Mapping[str, object] = field(default_factory=dict)
    error: str = ""

    @property
    def accepted(self) -> bool:
        return self.error == ""


def build_param_groups(
    schema: Sequence[ScriptInput], values: Mapping[str, object]
) -> tuple[ParamGroup, ...]:
    """Groups `schema` by `spec.group`, in declaration order, each field
    showing `values`' current value or its own declared default."""
    groups: dict[str, list[ParamField]] = {}
    for spec in schema:
        groups.setdefault(spec.group or "", []).append(_field(spec, values))
    return tuple(
        ParamGroup(label=label, fields=tuple(fields))
        for label, fields in groups.items()
    )


def validate_params(
    schema: Sequence[ScriptInput],
    raw: Mapping[str, object],
    construct: Callable[[Mapping[str, object]], object],
) -> ParamValidation:
    """Coerces `raw`'s text-shaped values into `schema`'s declared types,
    then calls `construct(parsed)` and discards the result — the script or
    strategy itself is the validator (its own `input_int()`/`input_float()`
    enforce `minval`/`maxval`), one check rather than two that could
    disagree."""
    parsed: dict[str, object] = {}
    for spec in schema:
        if spec.name not in raw:
            continue
        try:
            parsed[spec.name] = _coerce(spec, raw[spec.name])
        except (TypeError, ValueError):
            return ParamValidation(
                error=f"{spec.label}: invalid value ({raw[spec.name]!r})"
            )
    try:
        construct(parsed)
    except ValueError as exc:
        return ParamValidation(error=str(exc))
    return ParamValidation(values=parsed)


def _field(spec: ScriptInput, values: Mapping[str, object]) -> ParamField:
    return ParamField(
        name=spec.name,
        label=spec.label,
        kind=ParamKind(spec.kind.value),
        default=spec.default,
        value=values.get(spec.name, spec.default),
        minval=spec.minval,
        maxval=spec.maxval,
        options=tuple(spec.options) if spec.options else (),
        suffix=spec.suffix or "",
        step=spec.step,
    )


def _coerce(spec: ScriptInput, raw: object) -> object:
    if spec.kind is InputKind.INT:
        return int(str(raw).strip())
    if spec.kind is InputKind.FLOAT:
        value = float(str(raw).strip())
        if not math.isfinite(value):
            raise ValueError("must be finite")
        return value
    if spec.kind is InputKind.BOOL:
        return bool(raw)
    return str(raw)
