"""`EPIC-038L` - the shape a `--set key=value` must have to cross the command file."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.parameter_setting import (
    ParameterSetting,
)


@pytest.mark.parametrize(
    ("text", "key", "value"),
    [
        ("lower=81000", "lower", "81000"),
        ("lower=81000.5", "lower", "81000.5"),
        ("stop_loss=percent:5", "stop_loss", "percent:5"),
        ("spacing=GEOMETRIC", "spacing", "GEOMETRIC"),
        ("a=-1", "a", "-1"),
        ("k=" + "9" * 64, "k", "9" * 64),
        ("a1_b=x", "a1_b", "x"),
    ],
)
def test_a_setting_is_split_at_the_first_equals_sign(
    text: str, key: str, value: str
) -> None:
    assert ParameterSetting.parse(text) == ParameterSetting(key, value)


@pytest.mark.parametrize(
    "text",
    [
        "lower",
        "=81000",
        "lower=",
        "Lower=1",
        "1lower=1",
        "lower =1",
        "lower= 1",
        "lower=1 2",
        "lower=a=b",
        "lower='1'",
        "lower=1\n",
        "lower=1;x",
        "k" * 33 + "=1",
        "k=" + "9" * 65,
        "lower=١",
    ],
)
def test_a_text_that_is_not_a_setting_is_refused(text: str) -> None:
    with pytest.raises(ValueError, match=r"."):
        ParameterSetting.parse(text)


def test_the_refusal_never_repeats_the_value() -> None:
    with pytest.raises(ValueError) as refused:
        ParameterSetting.parse("lower=sec ret")

    assert "sec ret" not in str(refused.value)
