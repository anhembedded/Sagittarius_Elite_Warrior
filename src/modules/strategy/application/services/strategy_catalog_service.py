"""`StrategyCatalogService` — `IStrategyCatalog`'s implementation.

@details Everything `bot_params_form.py` used to do for a caller outside
this module, now done here instead of exported: the throwaway-instance
build, the `.inputs` read, the group-by-`spec.group` fold. Callers get
`core/contracts`' `ParamGroup`/`ParamField`, not the QML-era `list[dict]`
shape (`code-quality-rule.md` §1 forbids the loose dict crossing at all).
"""

from __future__ import annotations

import math
from collections.abc import Mapping

from Sagittarius_Elite_Warrior.src.core.contracts.param_field import (
    ParamField,
    ParamGroup,
    ParamKind,
)
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
from Sagittarius_Elite_Warrior.src.support.indicators.scripting import (
    InputKind,
    ScriptInput,
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
        groups: dict[str, list[ParamField]] = {}
        for spec in schema:
            groups.setdefault(spec.group or "", []).append(_field(spec, values))
        return tuple(
            ParamGroup(label=label, fields=tuple(fields))
            for label, fields in groups.items()
        )

    def validate_params(self, key: str, raw: Mapping[str, object]) -> ParamValidation:
        strategy_cls = self._require(key)
        schema = strategy_cls().inputs
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
            # Construct-and-discard: `BaseStrategy.__init__`'s own
            # `input_int()`/`input_float()` enforce each field's declared
            # `minval`/`maxval`, which type coercion alone does not — the
            # strategy itself is the validator, one check, not two that
            # could disagree (matches what `StrategyConfigCoordinator.
            # apply_bot_params()` did at the call site before this port
            # existed).
            strategy_cls(parsed)
        except ValueError as exc:
            return ParamValidation(error=str(exc))
        return ParamValidation(values=parsed)

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
