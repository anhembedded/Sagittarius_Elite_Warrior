from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from Sagittarius_Elite_Warrior.src.domain.scripting import InputKind, ScriptInput
from Sagittarius_Elite_Warrior.src.domain.strategies.base_strategy import BaseStrategy

#: Key used for fields whose ScriptInput.group is None — QML skips rendering
#: a group header when it sees this (an empty string, never a real group name).
UNGROUPED = ""


def build_bot_params_schema(
    strategy_cls: type[BaseStrategy],
    current_params: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    @brief Turns a strategy class's declared `input_*()` parameters
    (BOT-044/046) into the QML-ready shape the "Thông số Bot" modal's
    Repeater consumes: a list of groups, each holding its fields in
    declaration order.

    @param current_params Values to show as each field's current value
    (falls back to that field's own default when absent) — the schema
    itself (kind/minval/maxval/options/...) never changes with this, only
    which "value" each row reports.

    @details Builds one throwaway instance with no params to read `.inputs`
    — the declared schema is invariant regardless of params (a strategy's
    `setup()` always declares the same parameters), so `current_params` only
    ever affects the "value" field, never which fields exist.
    """
    schema = strategy_cls().inputs
    params = current_params or {}

    groups: dict[str, list[dict[str, Any]]] = {}
    for spec in schema:
        groups.setdefault(spec.group or UNGROUPED, []).append(_field_row(spec, params))

    return [{"group": name, "fields": fields} for name, fields in groups.items()]


def _field_row(spec: ScriptInput, params: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "name": spec.name,
        "label": spec.label,
        "kind": spec.kind.value,
        "default": spec.default,
        "value": params.get(spec.name, spec.default),
        "minval": spec.minval,
        "maxval": spec.maxval,
        "options": list(spec.options) if spec.options else [],
        "suffix": spec.suffix or "",
    }


def parse_bot_params(
    schema: Sequence[ScriptInput], raw_values: Mapping[str, Any]
) -> dict[str, Any]:
    """
    @brief Coerces raw values collected from the QML form (numeric fields
    arrive as text) into the types each field's `kind` declares.

    @details Deliberately does its own coercion rather than trusting
    `float()`/QML's own parsing: `float("nan")`/`float("inf")` both parse
    "successfully" yet would pass straight through the domain layer's own
    `isinstance(value, (int, float))` check un-caught (NaN/inf **are**
    floats) — silently producing an indicator fed a value that can never
    warm up correctly. Everything unparseable, including non-finite floats,
    raises `ValueError` here instead, with the field's own label in the
    message so the modal can show a message the user can act on.

    Only keys `schema` actually declares are read — an unrelated key in
    `raw_values` is ignored here (the domain layer's own
    "param nobody declares" guard, `BaseStrategy.__init__`, is the
    authoritative check once these coerced values are used to construct a
    real strategy instance).
    """
    parsed: dict[str, Any] = {}
    for spec in schema:
        if spec.name not in raw_values:
            continue
        raw = raw_values[spec.name]
        try:
            parsed[spec.name] = _coerce(spec, raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{spec.label}: giá trị không hợp lệ ({raw!r})") from exc
    return parsed


def _coerce(spec: ScriptInput, raw: Any) -> Any:
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
