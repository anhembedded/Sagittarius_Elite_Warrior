"""`EPIC-038L` - the Grid judges the parameters `bot edit` sets without the exchange.

The rules are `GridParams`'s own (the check asks it), so the tests state the business promise: an
unknown key is refused, a value that cannot be a Grid's is refused in words, a value that can be is
accepted, and what the bot already held is not blamed on this edit.
"""

from __future__ import annotations

from collections.abc import Mapping

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.parameter_setting import (
    ParameterSetting,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_parameter_check import (
    GRID_PARAMETER_KEYS,
    grid_parameter_problem,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
    GridParamsError,
)

_SPOT: dict[str, str] = {
    "lower": "100",
    "upper": "140",
    "grid_count": "4",
    "spacing": "ARITHMETIC",
    "capital_quote": "1000",
    "stop_loss": "price:90",
    "take_profit": "price:150",
}
_FUTURES: dict[str, str] = {**_SPOT, "direction": "LONG", "leverage": "3"}


def _after(held: Mapping[str, str], **set_: str) -> str | None:
    return grid_parameter_problem({**held, **set_}, set_.keys())


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("lower", "120"),
        ("lower", "99.5"),
        ("upper", "150"),
        ("grid_count", "30"),
        ("spacing", "GEOMETRIC"),
        ("spacing", "geometric"),
        ("capital_quote", "250.5"),
        ("stop_loss", "off"),
        ("stop_loss", "percent:5"),
        ("take_profit", "price:200"),
        ("take_profit", "percent:2.5"),
        ("on_range_exit", "close"),
    ],
)
def test_a_readable_value_of_a_grid_parameter_is_accepted(key: str, value: str) -> None:
    assert _after(_SPOT, **{key: value}) is None


@pytest.mark.parametrize(
    ("key", "value", "says"),
    [
        ("lower", "abc", "lower is not a number"),
        ("lower", "0", "lower must be positive"),
        ("lower", "-5", "lower must be positive"),
        ("lower", "NaN", "lower is not a finite number"),
        ("lower", "Infinity", "lower is not a finite number"),
        ("lower", "140", "upper must be above lower"),
        ("lower", "200", "upper must be above lower"),
        ("upper", "100", "upper must be above lower"),
        ("upper", "x", "upper is not a number"),
        ("grid_count", "0", "grid_count must be at least 1"),
        ("grid_count", "2.5", "grid_count is not a whole number"),
        ("grid_count", "-3", "grid_count is not a whole number"),
        ("spacing", "LOG", "spacing is not ARITHMETIC or GEOMETRIC"),
        ("capital_quote", "0", "capital_quote must be positive"),
        ("capital_quote", "lots", "capital_quote is not a number"),
        ("stop_loss", "10", "stop_loss is not off, price:<p> or percent:<n>"),
        ("stop_loss", "percent:100", "a stop_loss percent must be below 100"),
        ("stop_loss", "price:0", "a price exit needs a positive value"),
        ("take_profit", "percent:", "take_profit is not a number"),
        ("on_range_exit", "stop", "on_range_exit is not hold or close"),
    ],
)
def test_a_value_that_cannot_be_a_grids_is_refused_in_words(
    key: str, value: str, says: str
) -> None:
    problem = _after(_SPOT, **{key: value})

    assert problem is not None and says in problem


def test_a_key_that_is_not_a_grid_parameter_is_refused_and_named() -> None:
    problem = _after(_SPOT, leverge="3")

    assert problem is not None
    assert "leverge" in problem
    assert all(key in problem for key in GRID_PARAMETER_KEYS)


def test_every_declared_key_is_one_a_grid_reads() -> None:
    """The list a refusal offers is real: each key is one `GridParams.to_config` can write."""
    params = GridParams.from_config(
        _FUTURES | {"on_range_exit": "close", "trigger_price": "120"}
    )

    assert set(GRID_PARAMETER_KEYS) == set(params.to_config())


def test_the_two_ends_of_the_range_are_judged_against_each_other() -> None:
    assert _after(_SPOT, lower="130") is None
    assert _after(_SPOT, lower="150") is not None
    assert (
        grid_parameter_problem(
            {**_SPOT, "lower": "150", "upper": "200"}, {"lower", "upper"}
        )
        is None
    )


def test_the_owners_incident_lowering_the_range_to_include_the_price_is_accepted() -> (
    None
):
    held = {**_SPOT, "lower": "81305", "upper": "90000"}

    assert _after(held, lower="81000") is None


def test_a_range_set_on_a_bot_that_has_no_range_yet_is_judged_alone() -> None:
    """A DRAFT made with no parameters (`BOT-150`): lower is judged against nothing."""
    assert grid_parameter_problem({"lower": "5000"}, {"lower"}) is None
    assert grid_parameter_problem({"upper": "5"}, {"upper"}) is None
    assert grid_parameter_problem({"lower": "-1"}, {"lower"}) is not None


def test_what_the_bot_already_held_is_not_blamed_on_this_edit() -> None:
    held = {**_SPOT, "spacing": "LOG", "legacy_key": "x", "grid_count": ""}

    assert grid_parameter_problem({**held, "lower": "110"}, {"lower"}) is None


def test_direction_and_leverage_are_judged_as_the_pair_they_are() -> None:
    assert _after(_FUTURES, leverage="5") is None
    assert _after(_FUTURES, direction="SHORT") is None
    assert _after(_FUTURES, direction="UP") is not None
    assert _after(_FUTURES, leverage="0") is not None
    only_one = grid_parameter_problem({**_SPOT, "leverage": "3"}, {"leverage"})
    assert only_one is not None and "direction is missing" in only_one


def test_a_message_may_quote_the_value_which_the_setting_shape_has_already_limited() -> (
    None
):
    """`GridParamsError` quotes what it cannot read (`{text!r}`). That is why the shape of a setting's
    value (1-64 characters of `[A-Za-z0-9_.:+-]`, `ParameterSetting`) is judged before the kind sees it."""
    setting = ParameterSetting("lower", "sECRET")

    problem = _after(_SPOT, **{setting.key: setting.value})

    assert problem == "lower is not a number: 'sECRET'"


@pytest.mark.parametrize("held", [_SPOT, _FUTURES])
@pytest.mark.parametrize(
    ("key", "value"),
    [
        (key, value)
        for key, values in {
            "lower": ["50", "99", "0", "x", "140", "141", "1e2", "-1"],
            "upper": ["100", "101", "200", "x", "0", "-5"],
            "grid_count": ["0", "1", "12", "x", "1.5", " 3"],
            "spacing": ["GEOMETRIC", "LOG", "arithmetic"],
            "capital_quote": ["0", "1", "-1", "x"],
            "stop_loss": ["off", "price:1", "percent:99", "percent:100", "x", "price:"],
            "take_profit": ["off", "percent:1000", "price:-1", "x"],
            "leverage": ["1", "20", "0", "x", "2.5"],
            "direction": ["LONG", "SHORT", "NEUTRAL", "DOWN"],
            "on_range_exit": ["hold", "close", "nope"],
        }.items()
        for value in values
    ],
)
def test_the_check_agrees_with_the_parser_a_start_uses(
    held: dict[str, str], key: str, value: str
) -> None:
    """For a complete definition the verdict is exactly `GridParams.from_config`'s: no second rule."""
    merged = {**held, key: value}
    try:
        GridParams.from_config(merged)
        parser_accepts = True
    except GridParamsError:
        parser_accepts = False

    assert (grid_parameter_problem(merged, {key}) is None) is parser_accepts
