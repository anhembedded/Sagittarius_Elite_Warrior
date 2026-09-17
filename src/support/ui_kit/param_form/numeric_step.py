"""Pure arithmetic for one Up/Down/wheel step of a numeric `ParamField`.

`EPIC-025` PR 4.3m — moved here with `BotParamFieldWidget`: stepping a
value needs the field's own declared bounds, not a strategy. Was
`bot_params_form.step_numeric_param_value`, operating on the QML-era
`dict` row; now operates on the published `ParamField` dataclass.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from Sagittarius_Elite_Warrior.src.core.contracts.param_field import (
    ParamField,
    ParamKind,
)


def step_numeric_param_value(field: ParamField, raw_value: str, direction: int) -> str:
    """Return the schema-valid next numeric value without extra arithmetic
    at the caller.

    Invalid incomplete text intentionally remains untouched so a user can
    finish typing before the normal validation path reports an error.
    """
    if field.kind not in (ParamKind.INT, ParamKind.FLOAT) or direction not in (-1, 1):
        return raw_value
    try:
        current = Decimal(raw_value.strip())
        declared_step = field.step
        step = Decimal(
            str(
                declared_step
                if declared_step is not None
                else _default_step(field.kind)
            )
        )
        if not current.is_finite() or not step.is_finite() or step <= 0:
            return raw_value
        next_value = current + (Decimal(direction) * step)
        lower_bound = _decimal_bound(field.minval)
        upper_bound = _decimal_bound(field.maxval)
        if lower_bound is not None:
            next_value = max(lower_bound, next_value)
        if upper_bound is not None:
            next_value = min(upper_bound, next_value)
        if field.kind is ParamKind.INT:
            return str(int(next_value))
        return format(next_value, "f")
    except (InvalidOperation, ValueError):
        return raw_value


def _default_step(kind: ParamKind) -> int | float:
    return 1 if kind is ParamKind.INT else 0.1


def _decimal_bound(value: object) -> Decimal | None:
    if value is None:
        return None
    bound = Decimal(str(value))
    return bound if bound.is_finite() else None
