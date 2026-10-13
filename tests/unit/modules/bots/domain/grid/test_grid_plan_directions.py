"""`EPIC-039B` - one planner, three directions: only the opening exposure differs.

The levels (prices, sides, quantities) are the same for LONG, SHORT and NEUTRAL; what a
direction decides is the opening trade (a market buy of the SELL levels, a market sell of the
BUY levels, none) and which counters are reduce-only. Leverage scales the notional the ladder
may reach; at 1 it is today's capital rule. Spot's byte-for-byte proof is the recorded oracle
(`spot_oracle/`); these tests state what is new.
"""

from __future__ import annotations

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
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.report_example import (
    CONFIG,
    LAST_PRICE,
    TERMS,
)

D = Decimal


def _plan(
    direction: str = "LONG",
    leverage: str = "1",
    sizing: LevelSizing = LevelSizing.EQUAL_CAPITAL,
    last_price: Decimal = LAST_PRICE,
) -> GridPlan:
    config = {**CONFIG, "direction": direction, "leverage": leverage}
    return plan(GridParams.from_config(config), TERMS, last_price, sizing)


def _shape(grid_plan: GridPlan) -> list[tuple[int, Decimal, LevelSide, Decimal]]:
    return [(lv.index, lv.price, lv.side, lv.quantity) for lv in grid_plan.levels]


@pytest.mark.parametrize("sizing", list(LevelSizing))
def test_the_levels_are_the_same_for_every_direction(sizing: LevelSizing) -> None:
    long_, short, neutral = (
        _plan(d, "1", sizing) for d in ("LONG", "SHORT", "NEUTRAL")
    )

    assert _shape(long_) == _shape(short) == _shape(neutral)
    assert (
        long_.capital_per_level == short.capital_per_level == neutral.capital_per_level
    )


def test_long_opens_with_a_market_buy_of_the_sell_levels_quantity() -> None:
    grid_plan = _plan("LONG")

    assert grid_plan.direction is TradeDirection.LONG
    assert grid_plan.opening_quantity == sum(
        (lv.quantity for lv in grid_plan.sell_levels), D(0)
    )
    assert grid_plan.opening_quantity > 0
    assert grid_plan.opening_buy_quantity == grid_plan.opening_quantity


def test_short_opens_with_a_market_sell_of_the_buy_levels_quantity() -> None:
    grid_plan = _plan("SHORT")

    assert grid_plan.direction is TradeDirection.SHORT
    assert grid_plan.opening_quantity == -sum(
        (lv.quantity for lv in grid_plan.buy_levels), D(0)
    )
    assert grid_plan.opening_quantity < 0
    assert grid_plan.opening_buy_quantity == 0


def test_neutral_opens_nothing() -> None:
    grid_plan = _plan("NEUTRAL")

    assert grid_plan.direction is TradeDirection.NEUTRAL
    assert grid_plan.opening_quantity == 0
    assert grid_plan.opening_buy_quantity == 0


def test_the_counters_that_only_reduce_are_marked_reduce_only() -> None:
    """LONG's SELLs reduce a long and SHORT's BUYs reduce a short; NEUTRAL's can open."""
    long_, short, neutral = (_plan(d) for d in ("LONG", "SHORT", "NEUTRAL"))

    assert all(lv.reduce_only for lv in long_.sell_levels)
    assert not any(lv.reduce_only for lv in long_.buy_levels)
    assert all(lv.reduce_only for lv in short.buy_levels)
    assert not any(lv.reduce_only for lv in short.sell_levels)
    assert not any(lv.reduce_only for lv in neutral.levels)
    empty = [lv for lv in long_.levels if lv.side is LevelSide.EMPTY]
    assert empty
    assert not any(lv.reduce_only for lv in empty)


def test_leverage_scales_the_capital_the_ladder_may_reach() -> None:
    at_one, at_three = _plan("LONG", "1"), _plan("LONG", "3")

    assert at_three.capital_per_level == at_one.capital_per_level * 3


def test_equal_quantity_gives_every_order_the_same_base_quantity() -> None:
    grid_plan = _plan("NEUTRAL", "2", LevelSizing.EQUAL_QUANTITY)
    quantities = {lv.quantity for lv in grid_plan.order_levels}

    assert len(quantities) == 1
    assert quantities.pop() > 0


@pytest.mark.parametrize("direction", ["LONG", "SHORT", "NEUTRAL"])
@pytest.mark.parametrize("leverage", ["1", "3", "10"])
@pytest.mark.parametrize("last_price", [D(61000), LAST_PRICE, D(69000)])
def test_equal_quantity_never_reaches_more_notional_than_capital_times_leverage(
    direction: str, leverage: str, last_price: Decimal
) -> None:
    """O2: the worst case, every order filled, is at most capital x leverage.

    The price starts low, in the middle and high in the range: sizing by the last price
    would overshoot with the price low, where most of the levels are worth more.
    """
    grid_plan = _plan(direction, leverage, LevelSizing.EQUAL_QUANTITY, last_price)
    ceiling = D(CONFIG["capital_quote"]) * int(leverage)

    worst = sum((lv.notional for lv in grid_plan.order_levels), D(0))

    assert worst <= ceiling
    assert worst > ceiling * D("0.8")


def test_equal_quantity_is_not_the_default() -> None:
    """Spot's equal-capital rule is what a call without a sizing gets."""
    config = {**CONFIG}
    params = GridParams.from_config(config)

    assert plan(params, TERMS, LAST_PRICE) == plan(
        params, TERMS, LAST_PRICE, LevelSizing.EQUAL_CAPITAL
    )
