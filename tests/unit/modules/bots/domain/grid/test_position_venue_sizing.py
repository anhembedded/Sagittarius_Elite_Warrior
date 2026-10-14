"""`EPIC-039H` - a position venue's ladder is sized by quantity, from the venue's own limits.

@details The venue profile's `exposure_kind` is the one input: the plan judge, the readiness, the
preview and the executor all plan with the sizing it names, so no caller can forget to pass it and
draw a Spot-shaped Futures ladder (`LevelSizing`, `EPIC-039B`). A Spot venue plans as it always
did; the Spot oracle (`spot_oracle/`) pins that.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.trade_direction import (
    TradeDirection,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    SPOT_LIMITS,
    ExposureKind,
    ExposureLimits,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    BotKindInputs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_notional_cap import (
    allowed_notional,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_evaluation import (
    evaluate_grid,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_ladder import (
    buys_within_capital,
    runtime_from_plan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import (
    LevelSide,
    LevelSizing,
    plan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_reactions import (
    LadderRules,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_resume_plan import (
    resume_plan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.level_sizing_rule import (
    level_sizing_for,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_brackets import (
    LeverageBracket,
    LeverageBrackets,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerInventory,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.report_example import (
    CONFIG,
    LAST_PRICE,
    TERMS,
    inputs,
)

D = Decimal
_FUTURES_LIMITS = ExposureLimits(
    frozenset({TradeDirection.LONG}), 125, ExposureKind.POSITION
)
_CONFIG = {**CONFIG, "direction": "LONG", "leverage": "3", "stop_loss": "price:50000"}


def _futures_inputs(**changes: str) -> BotKindInputs:
    base = inputs(**{**_CONFIG, **changes})
    return BotKindInputs(base.config, base.terms, base.market, None, _FUTURES_LIMITS)


def test_a_position_venue_plans_with_one_quantity_at_every_level_and_spot_does_not() -> (
    None
):
    futures = evaluate_grid(_futures_inputs(), GridThresholds())
    spot = evaluate_grid(inputs(), GridThresholds())

    assert futures.plan is not None and spot.plan is not None
    assert futures.plan.level_sizing is LevelSizing.EQUAL_QUANTITY
    assert len({lv.quantity for lv in futures.plan.order_levels}) == 1
    assert spot.plan.level_sizing is LevelSizing.EQUAL_CAPITAL
    assert len({lv.quantity for lv in spot.plan.order_levels}) > 1


def test_the_sizing_follows_the_venues_exposure_kind_and_nothing_else() -> None:
    assert level_sizing_for(ExposureKind.POSITION) is LevelSizing.EQUAL_QUANTITY
    assert level_sizing_for(ExposureKind.INVENTORY) is LevelSizing.EQUAL_CAPITAL
    assert SPOT_LIMITS.exposure_kind is ExposureKind.INVENTORY


def test_a_futures_long_at_leverage_three_is_not_refused_by_the_plan_judge() -> None:
    """The limits default to Spot's, which would refuse the leverage: the venue's word counts."""
    evaluation = evaluate_grid(_futures_inputs(), GridThresholds())

    assert "LEVERAGE_NOT_ALLOWED" not in {v.code for v in evaluation.verdicts}
    assert not any(v.refuses for v in evaluation.verdicts), evaluation.verdicts
    without_the_venue = evaluate_grid(inputs(**_CONFIG), GridThresholds())
    assert any(v.refuses for v in without_the_venue.verdicts), "Spot's limits refuse it"


def test_a_direction_the_venue_does_not_allow_is_refused_in_one_sentence() -> None:
    evaluation = evaluate_grid(_futures_inputs(direction="SHORT"), GridThresholds())

    assert [v.code for v in evaluation.verdicts] == ["DIRECTION_NOT_ALLOWED"]


def test_every_counter_buy_of_a_position_ladder_buys_the_one_quantity() -> None:
    params = GridParams.from_config(_CONFIG)
    ladder = plan(params, TERMS, LAST_PRICE, LevelSizing.EQUAL_QUANTITY)

    runtime = runtime_from_plan(ladder, TERMS.step_size)

    assert ladder.uniform_quantity is not None
    assert {level.buy_quantity for level in runtime.levels} == {ladder.uniform_quantity}


def test_a_spot_ladders_counter_buys_still_buy_their_share_at_their_own_price() -> None:
    params = GridParams.from_config(CONFIG)
    ladder = plan(params, TERMS, LAST_PRICE)

    runtime = runtime_from_plan(ladder, TERMS.step_size)

    assert ladder.uniform_quantity is None
    assert len({level.buy_quantity for level in runtime.levels}) > 1


def test_a_resumed_position_ladder_keeps_its_quantity_until_the_capital_cannot_pay() -> (
    None
):
    params = GridParams.from_config(_CONFIG)
    rules = LadderRules(TERMS.step_size, TERMS.min_notional)
    ladder = plan(params, TERMS, LAST_PRICE, LevelSizing.EQUAL_QUANTITY)
    q = ladder.uniform_quantity
    assert q is not None

    plenty = buys_within_capital(ladder, D(1_000_000), rules)
    little = buys_within_capital(ladder, D(100), rules)

    assert {lv.quantity for lv in plenty.buy_levels} == {q}
    assert all(0 < lv.quantity < q for lv in little.buy_levels)
    assert all(lv.side is LevelSide.BUY for lv in little.buy_levels)


def test_a_resume_over_a_held_position_sizes_the_sells_to_it_and_the_buys_to_the_notional_left() -> (
    None
):
    params = GridParams.from_config(_CONFIG)
    held = OwnerInventory(D("0.05"), D("0.05") * LAST_PRICE)

    resumed = resume_plan(params, TERMS, LAST_PRICE, held, LevelSizing.EQUAL_QUANTITY)

    assert sum((lv.quantity for lv in resumed.sell_levels), D(0)) <= held.quantity
    assert resumed.opening_quantity == 0
    notional_left = params.capital_quote * params.leverage - held.cost
    assert sum((lv.notional for lv in resumed.buy_levels), D(0)) <= notional_left


def test_the_largest_position_a_symbol_allows_is_the_cap_of_the_highest_bracket_for_the_leverage() -> (
    None
):
    brackets = LeverageBrackets(
        "BTCUSDT",
        (
            LeverageBracket(1, 20, D(0), D(50_000), D("0.004"), D(0)),
            LeverageBracket(2, 10, D(50_000), D(250_000), D("0.005"), D(50)),
        ),
    )

    assert allowed_notional(brackets, 5) == D(250_000)
    assert allowed_notional(brackets, 10) == D(250_000)
    assert allowed_notional(brackets, 11) == D(50_000)
    assert allowed_notional(brackets, 21) == D(0), "no bracket allows it"
