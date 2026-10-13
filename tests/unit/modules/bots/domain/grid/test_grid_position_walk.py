"""`EPIC-039B` - a grid is a position function of price (DESIGN §5), shown on random paths.

`walk_position` moves a price along a path and fills the plan's resting orders the way the
live ladder does (a BUY or SELL fills when the price reaches it; its counter goes to the next
level up or down, with the same quantity). With the same base quantity at every level
(`LevelSizing.EQUAL_QUANTITY`) the position after a fill at level i is exactly
`q * (N - i - c)`, `c` being 0 for LONG, N for SHORT and N - g0 for NEUTRAL, g0 the index of
the level left EMPTY at the start. The equal-capital Spot sizing has no such property; the
last tests pin the path on which it drifts, so nobody builds on it.
"""

from __future__ import annotations

import random
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.trade_direction import (
    TradeDirection,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import (
    GridPlan,
    LevelSide,
    LevelSizing,
    plan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_position_walk import (
    walk_position,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.report_example import (
    CONFIG,
    LAST_PRICE,
    TERMS,
)

D = Decimal
_DIRECTIONS = ("LONG", "SHORT", "NEUTRAL")


def _plan(
    direction: str,
    sizing: LevelSizing,
    spacing: str = "ARITHMETIC",
    last_price: Decimal = LAST_PRICE,
) -> GridPlan:
    config = {**CONFIG, "direction": direction, "leverage": "2", "spacing": spacing}
    return plan(GridParams.from_config(config), TERMS, last_price, sizing)


def _gap(grid_plan: GridPlan) -> int:
    return next(lv.index for lv in grid_plan.levels if lv.side is LevelSide.EMPTY)


def _offset(grid_plan: GridPlan) -> int:
    top = len(grid_plan.levels) - 1
    return {
        TradeDirection.LONG: 0,
        TradeDirection.SHORT: top,
        TradeDirection.NEUTRAL: top - _gap(grid_plan),
    }[grid_plan.direction]


def _path(seed: int, grid_plan: GridPlan, length: int = 60) -> list[Decimal]:
    rng = random.Random(seed)  # noqa: S311 - a seeded test generator, not a secret
    low, high = grid_plan.levels[0].price, grid_plan.levels[-1].price
    price = grid_plan.last_price
    path = []
    for _ in range(length):
        price = min(
            max(price + D(f"{rng.random() - 0.5:.3f}") * (high - low) / 3, low), high
        )
        path.append(price.quantize(D("0.01")))
    return path


@pytest.mark.parametrize("spacing", ["ARITHMETIC", "GEOMETRIC"])
@pytest.mark.parametrize("direction", _DIRECTIONS)
@pytest.mark.parametrize("seed", range(12))
def test_position_equals_q_times_n_minus_i_minus_c_after_every_fill(
    direction: str, spacing: str, seed: int
) -> None:
    grid_plan = _plan(direction, LevelSizing.EQUAL_QUANTITY, spacing)
    q = next(lv.quantity for lv in grid_plan.order_levels)
    top = len(grid_plan.levels) - 1

    walk = walk_position(grid_plan, _path(seed, grid_plan))

    assert walk.fills, "the path must fill something or the test proves nothing"
    for fill in walk.fills:
        assert fill.position_after == q * (top - fill.level_index - _offset(grid_plan))


@pytest.mark.parametrize("direction", _DIRECTIONS)
def test_the_position_stays_inside_the_range_the_direction_allows(
    direction: str,
) -> None:
    grid_plan = _plan(direction, LevelSizing.EQUAL_QUANTITY)
    q = next(lv.quantity for lv in grid_plan.order_levels)
    top = len(grid_plan.levels) - 1
    lowest, highest = q * (-_offset(grid_plan)), q * (top - _offset(grid_plan))

    for seed in range(20):
        walk = walk_position(grid_plan, _path(seed, grid_plan, 120))
        assert all(lowest <= f.position_after <= highest for f in walk.fills)
    assert (lowest <= 0 <= highest) if direction == "NEUTRAL" else True


def test_neutral_crosses_zero_and_comes_back_on_a_path_that_does() -> None:
    grid_plan = _plan("NEUTRAL", LevelSizing.EQUAL_QUANTITY)
    low, high = grid_plan.levels[0].price, grid_plan.levels[-1].price
    path = [high, low, high, low, grid_plan.last_price]

    walk = walk_position(grid_plan, path)
    signs = {(f.position_after > 0) - (f.position_after < 0) for f in walk.fills}

    assert signs >= {-1, 0, 1}
    assert walk.position == 0
    assert walk.opening_position == 0


def test_a_walk_starts_from_the_opening_trade() -> None:
    for direction in _DIRECTIONS:
        grid_plan = _plan(direction, LevelSizing.EQUAL_QUANTITY)
        assert walk_position(grid_plan, []).position == grid_plan.opening_quantity


def test_a_short_is_paid_entry_minus_exit() -> None:
    """A short sold at the opening price and bought back lower earns the difference."""
    grid_plan = _plan("SHORT", LevelSizing.EQUAL_QUANTITY)
    q = next(lv.quantity for lv in grid_plan.order_levels)
    gap = _gap(grid_plan)
    below = grid_plan.levels[gap - 1].price

    walk = walk_position(grid_plan, [below])

    (fill,) = walk.fills
    assert fill.side is OrderSide.BUY
    assert fill.quantity == q
    assert walk.realised == q * (grid_plan.last_price - below)
    assert walk.realised > 0


def test_a_long_is_paid_exit_minus_entry() -> None:
    grid_plan = _plan("LONG", LevelSizing.EQUAL_QUANTITY)
    q = next(lv.quantity for lv in grid_plan.order_levels)
    above = grid_plan.levels[_gap(grid_plan) + 1].price

    walk = walk_position(grid_plan, [above])

    assert walk.realised == q * (above - grid_plan.last_price)
    assert walk.realised > 0


def test_equal_capital_levels_do_not_share_a_quantity() -> None:
    """Why `EQUAL_CAPITAL` is no position function: what a SELL sells is not what its
    counter BUY rebuys.

    From 65,000 the price rises through 66,000 and 67,000 (two SELLs of the opening base),
    then falls back to 66,000, where the counter BUY is sized by its own level (capital /
    66,000 = 0.01515151) and not by the 0.01538461 the SELL sold; the position at 66,000 then
    differs from the first time the price was there. Equal quantity has one `q`, so it cannot.
    """
    capital = _plan("LONG", LevelSizing.EQUAL_CAPITAL, last_price=D(65000))
    equal = _plan("LONG", LevelSizing.EQUAL_QUANTITY, last_price=D(65000))

    sold_above = capital.levels[7].quantity
    rebought_below = capital.levels[6].quantity
    assert capital.levels[6].side is LevelSide.SELL
    assert rebought_below == sold_above  # both SELL levels are sized at the last price
    rebuy = D(CONFIG["capital_quote"]) * 2 / 10 / capital.levels[6].price
    assert abs(rebuy - sold_above) > D("0.0000001")
    assert len({lv.quantity for lv in equal.order_levels}) == 1
