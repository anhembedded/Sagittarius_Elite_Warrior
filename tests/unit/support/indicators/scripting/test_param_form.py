from __future__ import annotations

from Sagittarius_Elite_Warrior.src.support.indicators.scripting import (
    InputKind,
    build_input,
)
from Sagittarius_Elite_Warrior.src.support.indicators.scripting.param_form import (
    build_param_groups,
    validate_params,
)


def _int_input(name: str, default: int, group: str | None = None):
    return build_input(InputKind.INT, name, default, None, 1, None, None, group)


def test_build_param_groups_folds_by_declared_group():
    schema = (
        _int_input("fast", 12, group="MACD"),
        _int_input("slow", 26, group="MACD"),
        _int_input("period", 20, group=None),
    )

    groups = build_param_groups(schema, {"fast": 10})

    labels = [group.label for group in groups]
    assert labels == ["MACD", ""]
    macd_group = groups[0]
    assert {field.name for field in macd_group.fields} == {"fast", "slow"}
    fast_field = next(f for f in macd_group.fields if f.name == "fast")
    assert fast_field.value == 10  # overridden
    slow_field = next(f for f in macd_group.fields if f.name == "slow")
    assert slow_field.value == 26  # falls back to schema default


def test_validate_params_coerces_and_runs_the_constructor_check():
    schema = (_int_input("period", 20),)
    seen: dict = {}

    def construct(parsed):
        seen.update(parsed)

    result = validate_params(schema, {"period": "50"}, construct)

    assert result.accepted
    assert result.values == {"period": 50}
    assert seen == {"period": 50}


def test_validate_params_rejects_a_non_numeric_value():
    schema = (_int_input("period", 20),)

    result = validate_params(schema, {"period": "not_a_number"}, lambda parsed: None)

    assert not result.accepted
    assert "period" in result.error.lower() or "Period" in result.error


def test_validate_params_rejects_when_the_constructor_raises():
    schema = (_int_input("period", 20),)

    def construct(parsed):
        raise ValueError("period must be at least 5")

    result = validate_params(schema, {"period": "1"}, construct)

    assert not result.accepted
    assert "period must be at least 5" in result.error


def test_validate_params_ignores_a_key_the_schema_never_declares():
    schema = (_int_input("period", 20),)

    result = validate_params(schema, {"unrelated": "1"}, lambda parsed: None)

    assert result.accepted
    assert "unrelated" not in result.values
