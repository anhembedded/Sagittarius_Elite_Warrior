"""`EPIC-039B` - a Grid's direction and leverage: new keys, and what a saved definition becomes.

A definition saved before the epic holds neither key and loads as LONG at leverage 1 through
one named function; it is written back without them, so a Spot definition on disk is the same
bytes after this task as before. A definition that names a direction is read strictly, and one
for a position venue must name both.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.trade_direction import (
    TradeDirection,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    LEGACY_DIRECTION,
    LEGACY_LEVERAGE,
    GridParams,
    GridParamsError,
    exposure_of_a_saved_definition,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.report_example import (
    CONFIG,
)


def test_a_definition_saved_before_the_epic_loads_as_long_at_leverage_one() -> None:
    params = GridParams.from_config(CONFIG)

    assert params.direction is TradeDirection.LONG
    assert params.leverage == 1
    assert (LEGACY_DIRECTION, LEGACY_LEVERAGE) == (TradeDirection.LONG, 1)


def test_the_migration_is_one_named_function_that_answers_for_absent_keys_only() -> (
    None
):
    assert exposure_of_a_saved_definition(CONFIG) == (TradeDirection.LONG, 1)
    assert exposure_of_a_saved_definition(
        {**CONFIG, "direction": "SHORT", "leverage": "3"}
    ) == (TradeDirection.SHORT, 3)


def test_a_long_grid_at_leverage_one_is_written_back_without_the_new_keys() -> None:
    """The bytes of a Spot definition do not change by being loaded and saved."""
    assert GridParams.from_config(CONFIG).to_config() == CONFIG


@pytest.mark.parametrize(
    ("direction", "leverage"),
    [("SHORT", "1"), ("NEUTRAL", "5"), ("LONG", "3")],
)
def test_a_direction_and_a_leverage_round_trip(direction: str, leverage: str) -> None:
    config = {**CONFIG, "direction": direction, "leverage": leverage}
    params = GridParams.from_config(config)

    assert params.direction is TradeDirection[direction]
    assert params.leverage == int(leverage)
    assert params.to_config()["direction"] == direction
    assert params.to_config()["leverage"] == leverage
    assert GridParams.from_config(params.to_config()) == params


def test_the_direction_ignores_case_and_whitespace() -> None:
    params = GridParams.from_config(
        {**CONFIG, "direction": " neutral ", "leverage": "2"}
    )

    assert params.direction is TradeDirection.NEUTRAL


@pytest.mark.parametrize("key", ["direction", "leverage"])
def test_naming_only_one_of_the_two_names_the_other(key: str) -> None:
    other = "leverage" if key == "direction" else "direction"
    config = {**CONFIG, key: "LONG" if key == "direction" else "2"}

    with pytest.raises(GridParamsError, match=other):
        GridParams.from_config(config)


@pytest.mark.parametrize("bad", ["UP", "", "long short"])
def test_an_unreadable_direction_names_the_key(bad: str) -> None:
    with pytest.raises(GridParamsError, match="direction"):
        GridParams.from_config({**CONFIG, "direction": bad, "leverage": "1"})


@pytest.mark.parametrize("bad", ["0", "-2", "2.5", "x", ""])
def test_an_unreadable_leverage_names_the_key(bad: str) -> None:
    with pytest.raises(GridParamsError, match="leverage"):
        GridParams.from_config({**CONFIG, "direction": "LONG", "leverage": bad})


@pytest.mark.parametrize("key", ["direction", "leverage"])
def test_a_definition_for_a_position_venue_must_name_both(key: str) -> None:
    config = {**CONFIG, "direction": "LONG", "leverage": "2"}
    del config[key]

    with pytest.raises(GridParamsError, match=key):
        GridParams.from_config_naming_exposure(config)


def test_a_definition_for_a_position_venue_that_names_both_reads() -> None:
    params = GridParams.from_config_naming_exposure(
        {**CONFIG, "direction": "NEUTRAL", "leverage": "4"}
    )

    assert (params.direction, params.leverage) == (TradeDirection.NEUTRAL, 4)
