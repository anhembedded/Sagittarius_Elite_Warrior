"""`EPIC-029C` — the ladder: sides, the EMPTY level, rounding direction, quantities."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
    GridSpacing,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import (
    GridPlan,
    LevelSide,
    plan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_spacing import (
    arithmetic_step,
    geometric_ratio,
    raw_levels,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.report_example import (
    CONFIG,
    LAST_PRICE,
    TERMS,
)

PARAMS = GridParams.from_config(CONFIG)


def _plan(last_price: Decimal = LAST_PRICE, **changes: str) -> GridPlan:
    return plan(GridParams.from_config({**CONFIG, **changes}), TERMS, last_price)


def _sides(grid_plan: GridPlan) -> list[str]:
    return [level.side.value[0] for level in grid_plan.levels]


def test_levels_below_are_buy_above_are_sell_and_the_nearest_is_empty() -> None:
    assert _sides(_plan()) == list("BBBBBESSSSS")


@pytest.mark.parametrize(
    ("last_price", "expected"),
    [
        (Decimal(65400), "BBBBBESSSSS"),  # within half a step of 65,000
        (Decimal(65500), "BBBBBESSSSS"),  # a tie goes to the lower level
        (Decimal("65500.01"), "BBBBBBESSSS"),  # now 66,000 is nearer
        (Decimal(60000), "ESSSSSSSSSS"),  # at the lower edge
        (Decimal(70000), "BBBBBBBBBBE"),  # at the upper edge
        (Decimal(50000), "SSSSSSSSSSS"),  # below the range: every level sells
        (Decimal(80000), "BBBBBBBBBBB"),  # above the range: every level buys
    ],
)
def test_sides_and_the_empty_level(last_price: Decimal, expected: str) -> None:
    assert "".join(_sides(_plan(last_price))) == expected


def test_capital_is_split_over_the_levels_that_hold_an_order() -> None:
    assert _plan().capital_per_level == Decimal(1000)
    assert _plan(Decimal(50000)).capital_per_level == Decimal(10000) / 11


def test_buy_quantities_are_capital_at_their_own_price_sell_at_the_last_price() -> None:
    grid_plan = plan(PARAMS, replace(TERMS, step_size=Decimal("0.00001")), LAST_PRICE)
    for level in grid_plan.buy_levels:
        exact = Decimal(1000) / level.price
        assert level.quantity <= exact < level.quantity + Decimal("0.00001")
    for level in grid_plan.sell_levels:
        assert level.quantity == Decimal("0.01538")  # 1,000 / 65,000 rounded down


def test_quantities_never_exceed_the_level_capital() -> None:
    grid_plan = plan(PARAMS, replace(TERMS, step_size=Decimal("0.001")), LAST_PRICE)
    for level in grid_plan.buy_levels:
        assert level.notional <= grid_plan.capital_per_level
        assert level.quantity % Decimal("0.001") == 0


def test_the_opening_purchase_is_the_total_of_the_sell_levels() -> None:
    grid_plan = _plan()
    assert grid_plan.opening_buy_quantity == sum(
        (level.quantity for level in grid_plan.sell_levels), Decimal(0)
    )
    assert grid_plan.opening_buy_quantity > 0


def test_the_empty_level_holds_nothing() -> None:
    empty = [level for level in _plan().levels if level.side is LevelSide.EMPTY]
    assert [(level.price, level.quantity) for level in empty] == [(Decimal(65000), 0)]


def test_buy_prices_round_down_and_sell_prices_round_up_to_the_tick() -> None:
    """Geometric levels are not multiples of the tick, so rounding shows its direction."""
    terms = replace(TERMS, tick_size=Decimal(1))
    params = GridParams.from_config({**CONFIG, "spacing": "GEOMETRIC"})
    raw = raw_levels(
        params.lower, params.upper, params.grid_count, GridSpacing.GEOMETRIC
    )
    grid_plan = plan(params, terms, LAST_PRICE)
    for level, raw_price in zip(grid_plan.levels, raw, strict=True):
        assert level.price % 1 == 0
        if level.side is LevelSide.SELL:
            assert raw_price <= level.price < raw_price + 1
        else:
            assert raw_price - 1 < level.price <= raw_price
    assert any(
        level.price != raw_price
        for level, raw_price in zip(grid_plan.levels, raw, strict=True)
    )


def test_arithmetic_levels() -> None:
    assert arithmetic_step(Decimal(60000), Decimal(70000), 10) == Decimal(1000)
    assert raw_levels(Decimal(60000), Decimal(70000), 4, GridSpacing.ARITHMETIC) == (
        Decimal(60000),
        Decimal(62500),
        Decimal(65000),
        Decimal(67500),
        Decimal(70000),
    )


def test_geometric_levels_multiply_by_the_ratio_and_end_exactly_at_upper() -> None:
    levels = raw_levels(Decimal(100), Decimal(400), 2, GridSpacing.GEOMETRIC)
    assert (
        geometric_ratio(Decimal(100), Decimal(400), 2).quantize(Decimal("1e-20")) == 2
    )
    assert levels[0] == 100
    assert levels[1].quantize(Decimal("1e-20")) == 200
    assert levels[2] == 400


@pytest.mark.parametrize(
    ("last_price", "expected"),
    [
        (Decimal(59500), "ESSSSSSSSSS"),  # exactly half the edge grid below
        (Decimal("59499.99"), "SSSSSSSSSSS"),  # just beyond half the edge grid
        (Decimal(59400), "SSSSSSSSSSS"),  # within one step, but beyond half
        (Decimal(70500), "BBBBBBBBBBE"),
        (Decimal("70500.01"), "BBBBBBBBBBB"),
    ],
)
def test_beyond_an_edge_only_half_the_edge_grid_keeps_a_level_empty(
    last_price: Decimal, expected: str
) -> None:
    assert "".join(_sides(_plan(last_price))) == expected


def test_geometric_half_step_is_measured_in_the_grid_the_price_sits_in() -> None:
    """Geometric 100–400 in 2 grids: levels 100, 200, 400. At 290 the price is in
    the 200–400 grid, 90 above 200 and within half of that grid (100), so 200 is
    EMPTY; measured against the grid below (half of 100 is 50) it would not be."""
    grid_plan = plan(
        GridParams.from_config(
            {
                **CONFIG,
                "lower": "100",
                "upper": "400",
                "grid_count": "2",
                "spacing": "GEOMETRIC",
            }
        ),
        replace(TERMS, tick_size=Decimal(1)),
        Decimal(290),
    )
    assert "".join(_sides(grid_plan)) == "BES"
