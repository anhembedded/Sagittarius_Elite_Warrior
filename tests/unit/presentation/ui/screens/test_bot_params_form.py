"""
Tests for `bot_params_form.py` (BOT-047) — the pure-Python schema/parsing
layer behind the "Thông số Bot" modal. No Qt/QML involved: these prove the
grouping and value-coercion logic in isolation before any QML round trip.
"""

import pytest

from Sagittarius_Elite_Warrior.src.domain.strategies.base_strategy import BaseStrategy
from Sagittarius_Elite_Warrior.src.domain.strategies.ema_crossover_strategy import (
    EmaCrossoverStrategy,
)
from Sagittarius_Elite_Warrior.src.domain.strategies.strategy_context import (
    StrategyContext,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.bot_params_form import (
    build_bot_params_rows,
    build_bot_params_schema,
    parse_bot_params,
    step_numeric_param_value,
)


class _RichParamsStrategy(BaseStrategy):
    """Declares one of every kind, across 2 groups — mirrors the mockup's
    "Quản lý Rủi ro" / "Chỉ số Kỹ thuật" split."""

    def setup(self) -> None:
        self.period = self.input_int(
            "period",
            20,
            label="Period",
            minval=1,
            maxval=200,
            group="Kỹ thuật",
            step=5,
        )
        self.threshold = self.input_float(
            "threshold",
            1.5,
            label="Ngưỡng",
            minval=0.0,
            group="Rủi ro",
            suffix="%",
            step=0.25,
        )
        self.enabled = self.input_bool("enabled", True, label="Bật", group="Rủi ro")
        self.mode = self.input_string(
            "mode", "fast", options=["fast", "slow"], label="Chế độ", group="Kỹ thuật"
        )

    def build_indicators(self) -> dict:
        return {}

    def decide(self, context: StrategyContext):
        return self.hold()


class _NoParamsStrategy(BaseStrategy):
    def build_indicators(self) -> dict:
        return {}

    def decide(self, context: StrategyContext):
        return self.hold()


# --------------------------------------------------------------------------
# build_bot_params_schema
# --------------------------------------------------------------------------


def test_a_strategy_with_no_params_produces_no_groups():
    assert build_bot_params_schema(_NoParamsStrategy) == []


def test_fields_are_grouped_by_declared_group_in_declaration_order():
    schema = build_bot_params_schema(_RichParamsStrategy)

    assert [group["group"] for group in schema] == ["Kỹ thuật", "Rủi ro"]
    assert [f["name"] for f in schema[0]["fields"]] == ["period", "mode"]
    assert [f["name"] for f in schema[1]["fields"]] == ["threshold", "enabled"]


def test_each_row_carries_everything_the_form_needs():
    schema = build_bot_params_schema(_RichParamsStrategy)
    period_row = schema[0]["fields"][0]

    assert period_row == {
        "name": "period",
        "label": "Period",
        "kind": "int",
        "default": 20,
        "value": 20,
        "minval": 1,
        "maxval": 200,
        "options": [],
        "suffix": "",
        "step": 5,
    }


def test_schema_preserves_an_explicit_float_step():
    schema = build_bot_params_schema(_RichParamsStrategy)
    threshold_row = schema[1]["fields"][0]

    assert threshold_row["step"] == 0.25


def test_string_field_carries_its_options():
    schema = build_bot_params_schema(_RichParamsStrategy)
    mode_row = schema[0]["fields"][1]

    assert mode_row["options"] == ["fast", "slow"]


def test_value_falls_back_to_default_when_no_current_params_given():
    schema = build_bot_params_schema(_RichParamsStrategy, current_params=None)

    period_row = schema[0]["fields"][0]
    assert period_row["value"] == period_row["default"] == 20


def test_value_reflects_current_params_when_given():
    schema = build_bot_params_schema(_RichParamsStrategy, current_params={"period": 55})

    period_row = schema[0]["fields"][0]
    assert period_row["value"] == 55
    assert period_row["default"] == 20  # unchanged — needed for "Reset"


def test_current_params_missing_a_field_still_falls_back_to_its_default():
    schema = build_bot_params_schema(_RichParamsStrategy, current_params={"period": 55})

    mode_row = schema[0]["fields"][1]
    assert mode_row["value"] == "fast"


def test_ema_crossover_strategy_schema_matches_its_real_declared_periods():
    """The actual production strategy (BOT-046), not just a test double."""
    schema = build_bot_params_schema(EmaCrossoverStrategy)

    assert len(schema) == 1
    fields = {f["name"]: f for f in schema[0]["fields"]}
    assert fields["fast_period"]["default"] == 12
    assert fields["slow_period"]["default"] == 26
    assert fields["fast_period"]["kind"] == "int"


def test_presentation_rows_are_prepared_in_python_not_flattened_by_qml():
    rows = build_bot_params_rows(build_bot_params_schema(_RichParamsStrategy))

    assert [(row["rowType"], row["groupLabel"]) for row in rows] == [
        ("header", "Kỹ thuật"),
        ("field", ""),
        ("field", ""),
        ("header", "Rủi ro"),
        ("field", ""),
        ("field", ""),
    ]
    assert rows[1]["field"]["name"] == "period"


@pytest.mark.parametrize(
    ("field", "current", "direction", "expected"),
    [
        ({"kind": "int", "step": 5, "minval": 1, "maxval": 20}, "15", 1, "20"),
        ({"kind": "int", "step": 5, "minval": 1, "maxval": 20}, "1", -1, "1"),
        (
            {"kind": "float", "step": 0.25, "minval": 0.0, "maxval": 2.0},
            "1.5",
            1,
            "1.75",
        ),
        (
            {"kind": "float", "step": None, "minval": None, "maxval": None},
            "1.2",
            -1,
            "1.1",
        ),
    ],
)
def test_numeric_step_is_normalized_by_python_schema_rule(
    field, current, direction, expected
):
    assert step_numeric_param_value(field, current, direction) == expected


def test_numeric_step_leaves_incomplete_or_non_numeric_text_untouched():
    field = {"kind": "float", "step": 0.1, "minval": None, "maxval": None}

    assert step_numeric_param_value(field, "-", 1) == "-"


# --------------------------------------------------------------------------
# parse_bot_params
# --------------------------------------------------------------------------


def _schema():
    return _RichParamsStrategy().inputs


def test_parses_every_kind_together_from_qml_shaped_raw_values():
    parsed = parse_bot_params(
        _schema(),
        {"period": "50", "threshold": "2.5", "enabled": True, "mode": "slow"},
    )

    assert parsed == {
        "period": 50,
        "threshold": 2.5,
        "enabled": True,
        "mode": "slow",
    }


def test_parses_int_field_from_string():
    assert parse_bot_params(_schema(), {"period": "50"}) == {"period": 50}


def test_parses_float_field_from_string():
    assert parse_bot_params(_schema(), {"threshold": "2.5"}) == {"threshold": 2.5}


def test_parses_bool_field():
    assert parse_bot_params(_schema(), {"enabled": False}) == {"enabled": False}


def test_parses_string_field():
    assert parse_bot_params(_schema(), {"mode": "slow"}) == {"mode": "slow"}


def test_ignores_keys_the_schema_does_not_declare():
    assert parse_bot_params(_schema(), {"typo_period": "50"}) == {}


def test_unparseable_int_raises_with_the_fields_label():
    with pytest.raises(ValueError, match="Period: giá trị không hợp lệ"):
        parse_bot_params(_schema(), {"period": "abc"})


def test_unparseable_float_raises():
    with pytest.raises(ValueError, match="Ngưỡng"):
        parse_bot_params(_schema(), {"threshold": "not-a-number"})


@pytest.mark.parametrize("bad", ["nan", "inf", "-inf"])
def test_non_finite_float_raises_instead_of_silently_passing_through(bad):
    """float("nan")/float("inf") parse "successfully" in Python but must
    never reach a real indicator — NaN/inf are still floats, so the domain
    layer's isinstance(value, (int, float)) check alone would not catch
    them."""
    with pytest.raises(ValueError, match="Ngưỡng"):
        parse_bot_params(_schema(), {"threshold": bad})


def test_empty_dict_of_raw_values_parses_to_an_empty_dict():
    assert parse_bot_params(_schema(), {}) == {}
