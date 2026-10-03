"""`EPIC-029C` — reading the user's Grid parameters: no hidden default, errors name the key."""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    ExitKind,
    ExitLevel,
    GridParams,
    GridParamsError,
    GridSpacing,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.report_example import (
    CONFIG,
)


def test_the_report_example_reads() -> None:
    params = GridParams.from_config(CONFIG)
    assert params.lower == Decimal(60000)
    assert params.upper == Decimal(70000)
    assert params.grid_count == 10
    assert params.spacing is GridSpacing.ARITHMETIC
    assert params.capital_quote == Decimal(10000)
    assert params.stop_loss_price == Decimal(57000)
    assert params.take_profit_price == Decimal(73500)


def test_a_round_trip_through_the_config_is_lossless() -> None:
    params = GridParams.from_config(
        {**CONFIG, "stop_loss": "price:55000.5", "take_profit": "off"}
    )
    assert GridParams.from_config(params.to_config()) == params


@pytest.mark.parametrize("key", sorted(CONFIG))
def test_every_key_is_required_and_named_when_missing(key: str) -> None:
    config = {k: v for k, v in CONFIG.items() if k != key}
    with pytest.raises(GridParamsError, match=key):
        GridParams.from_config(config)


def test_spacing_and_exits_ignore_case_and_whitespace() -> None:
    params = GridParams.from_config(
        {
            **CONFIG,
            "spacing": " geometric ",
            "stop_loss": " OFF ",
            "take_profit": "Price:80000",
        }
    )
    assert params.spacing is GridSpacing.GEOMETRIC
    assert params.stop_loss_price is None
    assert params.take_profit_price == Decimal(80000)


@pytest.mark.parametrize(
    ("kind", "edge", "below", "above"),
    [
        (
            ExitLevel(ExitKind.PERCENT, Decimal(5)),
            Decimal(100),
            Decimal(95),
            Decimal(105),
        ),
        (
            ExitLevel(ExitKind.PRICE, Decimal(90)),
            Decimal(100),
            Decimal(90),
            Decimal(90),
        ),
        (ExitLevel(ExitKind.OFF), Decimal(100), None, None),
    ],
)
def test_exit_levels_resolve_against_their_edge(
    kind: ExitLevel, edge: Decimal, below: Decimal | None, above: Decimal | None
) -> None:
    assert kind.below(edge) == below
    assert kind.above(edge) == above


@pytest.mark.parametrize(
    "changes",
    [
        {"lower": "0"},
        {"upper": "60000"},
        {"capital_quote": "-1"},
        {"grid_count": "-3"},
        {"lower": "Infinity"},
        {"stop_loss": "price:0"},
        {"stop_loss": "off:5"},
    ],
)
def test_invalid_values_are_refused(changes: dict[str, str]) -> None:
    with pytest.raises(GridParamsError):
        GridParams.from_config({**CONFIG, **changes})
