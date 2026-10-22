"""`EPIC-046A` - the trigger price is a limit on the entry: a better price opens the gate (ADR 046 D1, D4).

The range is 100-140 and the trigger 125. A LONG grid wants the price at or below the trigger, a
SHORT grid at or above it; the range is judged first and always.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.trade_direction import (
    TradeDirection,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_entry_gate import (
    EntryGate,
    entry_gate,
    entry_price,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_parameter_check import (
    grid_parameter_problem,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
    GridParamsError,
)

D = Decimal
_CONFIG = {
    "lower": "100",
    "upper": "140",
    "grid_count": "10",
    "spacing": "ARITHMETIC",
    "capital_quote": "1000",
    "stop_loss": "off",
    "take_profit": "off",
}


def _params(direction: str = "LONG", trigger: str | None = "125") -> GridParams:
    config = {**_CONFIG, "direction": direction, "leverage": "1"}
    if trigger is not None:
        config["trigger_price"] = trigger
    return GridParams.from_config(config)


@pytest.mark.parametrize(
    ("price", "gate"),
    [
        (D(99), EntryGate.OUTSIDE_RANGE),
        (D(100), EntryGate.OPEN),
        (D(125), EntryGate.OPEN),
        (D("125.01"), EntryGate.TRIGGER_NOT_MET),
        (D(140), EntryGate.TRIGGER_NOT_MET),
        (D("140.01"), EntryGate.OUTSIDE_RANGE),
    ],
    ids=["below", "lower", "at-trigger", "above-trigger", "upper", "above"],
)
def test_a_long_grid_enters_at_or_below_its_trigger(
    price: Decimal, gate: EntryGate
) -> None:
    assert entry_gate(_params("LONG"), price) is gate


@pytest.mark.parametrize(
    ("price", "gate"),
    [
        (D(99), EntryGate.OUTSIDE_RANGE),
        (D(100), EntryGate.TRIGGER_NOT_MET),
        (D("124.99"), EntryGate.TRIGGER_NOT_MET),
        (D(125), EntryGate.OPEN),
        (D(140), EntryGate.OPEN),
        (D("140.01"), EntryGate.OUTSIDE_RANGE),
    ],
    ids=["below", "lower", "under-trigger", "at-trigger", "upper", "above"],
)
def test_a_short_grid_enters_at_or_above_its_trigger(
    price: Decimal, gate: EntryGate
) -> None:
    assert entry_gate(_params("SHORT"), price) is gate


@pytest.mark.parametrize("price", [D(99), D(120), D(139), D(141)])
def test_a_grid_without_a_trigger_is_gated_by_the_range_alone(price: Decimal) -> None:
    expected = EntryGate.OPEN if 100 <= price <= 140 else EntryGate.OUTSIDE_RANGE
    assert entry_gate(_params(trigger=None), price) is expected


def test_the_entry_price_is_the_price_pulled_into_the_range_and_to_the_trigger() -> (
    None
):
    long = _params("LONG")
    short = _params("SHORT")

    assert entry_price(long, D(135)) == D(125), "above the trigger: it will enter at it"
    assert entry_price(long, D(120)) == D(120), "already better: it enters here"
    assert entry_price(long, D(150)) == D(125), (
        "pulled to the bound, then to the trigger"
    )
    assert entry_price(short, D(110)) == D(125)
    assert entry_price(short, D(130)) == D(130)
    assert entry_price(_params(trigger=None), D(90)) == D(100)


def test_a_trigger_outside_the_range_is_refused_in_words() -> None:
    for bad in ("99", "140.5"):
        with pytest.raises(GridParamsError, match="inside the range 100-140"):
            _params(trigger=bad)
    assert _params(trigger="100").trigger_price == D(100)
    assert _params(trigger="140").trigger_price == D(140)


def test_a_neutral_grid_refuses_a_trigger_in_words() -> None:
    with pytest.raises(GridParamsError, match="LONG or SHORT"):
        _params("NEUTRAL")
    assert _params("NEUTRAL", trigger=None).trigger_price is None


def test_the_trigger_round_trips_through_the_definition_and_a_blank_is_none() -> None:
    params = _params("SHORT")

    assert params.to_config()["trigger_price"] == "125"
    assert GridParams.from_config(params.to_config()).trigger_price == D(125)
    assert "trigger_price" not in _params(trigger=None).to_config()
    assert _params(trigger="  ").trigger_price is None
    assert _params(trigger="off").trigger_price is None, "how `bot edit` clears it"
    assert _params(direction=TradeDirection.LONG.name).direction is TradeDirection.LONG


def test_a_trigger_that_is_not_a_number_names_its_key() -> None:
    with pytest.raises(GridParamsError, match="trigger_price is not a number"):
        _params(trigger="soon")


def test_bot_edit_judges_the_trigger_against_the_range_and_the_direction() -> None:
    config = {**_CONFIG, "direction": "LONG", "leverage": "1", "trigger_price": "125"}
    assert grid_parameter_problem(config, ["trigger_price"]) is None
    assert grid_parameter_problem({**config, "trigger_price": "150"}, ["trigger_price"])
    assert grid_parameter_problem({**config, "upper": "120"}, ["upper"]), (
        "a range edit that leaves the trigger outside is refused"
    )
    assert grid_parameter_problem({**config, "direction": "NEUTRAL"}, ["direction"]), (
        "a direction change that leaves a trigger on a NEUTRAL grid is refused"
    )
