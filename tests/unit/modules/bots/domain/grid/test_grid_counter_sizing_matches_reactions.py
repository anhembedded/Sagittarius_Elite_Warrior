"""`BUG-212` - the Plan's counter-order sizing is held to what the real reactions emit.

`grid_order_sizing.sized_orders` judges, before Start, the counter orders the run will send. The
run sends them from `grid_reactions.on_fill`. Every order the start lays is filled whole through
the real `on_fill` (a BUY paying its fee in base, as Spot does) and the counter it emits must be
one the Plan sized, must not sell base the fill did not deliver, and, for a plan the check passes,
must meet the exchange's minimum and step.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    ExchangeTerms,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_evaluation import (
    evaluate_grid,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_ladder import (
    ladder_orders,
    runtime_from_plan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_order_sizing import (
    OrderOrigin,
    opening_ladder,
    sized_orders,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_reactions import (
    LevelFill,
    PlaceOrder,
    accepted,
    on_fill,
    placed,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.report_example import (
    inputs,
)

D = Decimal
_OWNER = {
    "lower": "2348",
    "upper": "2667",
    "stop_loss": "price:2259",
    "take_profit": "price:2805",
}
_OID = "SEW-test-0001"


def _terms(step: str, fee: str) -> ExchangeTerms:
    return ExchangeTerms(
        tick_size=D("0.01"),
        step_size=D(step),
        min_notional=D(5),
        maker_fee=D(fee),
        taker_fee=D(fee),
        max_notional_per_order=D(100000),
        max_open_orders=200,
    )


def _counter_after_filling(plan, terms, action):
    """The counter the real reactions emit when `action`, alone on the ladder, fills whole."""
    runtime = runtime_from_plan(plan, terms.step_size)
    laid = accepted(placed(runtime, action, _OID), _OID)
    base_fee = action.quantity * terms.taker_fee if action.side is OrderSide.BUY else 0
    fill = LevelFill(_OID, action.price, action.quantity, D(base_fee))
    reaction = on_fill(laid, fill, terms.step_size, hold=False)
    counters = [a for a in reaction.actions if isinstance(a, PlaceOrder)]
    return reaction, counters


@pytest.mark.parametrize("fee", ["0.001", "0.00075"])
@pytest.mark.parametrize("step", ["0.01", "0.001", "0.0001"])
@pytest.mark.parametrize("capital", ["35", "71.27", "120", "400"])
@pytest.mark.parametrize("grids", [4, 7, 11])
@pytest.mark.parametrize("price", ["2300", "2420", "2600"])
def test_every_counter_the_reactions_emit_is_one_the_plan_sized(
    fee: str, step: str, capital: str, grids: int, price: str
) -> None:
    terms = _terms(step, fee)
    evaluation = evaluate_grid(
        inputs(
            terms,
            D(price),
            **{**_OWNER, "capital_quote": capital, "grid_count": str(grids)},
        ),
        GridThresholds(),
    )
    plan = evaluation.plan
    assert plan is not None
    passes = not any(v.code == "LEVEL_BELOW_MIN_NOTIONAL" for v in evaluation.verdicts)
    sized = {
        (o.level_index, o.side): o.quantity
        for o in sized_orders(plan, terms)
        if o.origin is OrderOrigin.COUNTER
    }

    for action in ladder_orders(opening_ladder(plan, terms)):
        reaction, counters = _counter_after_filling(plan, terms, action)
        for counter in counters:
            assert sized[(counter.level_index, counter.side)] == counter.quantity
            assert counter.quantity % terms.step_size == 0
            if counter.side is OrderSide.SELL:
                assert counter.quantity <= reaction.runtime.inventory
            if passes:
                assert counter.quantity * counter.price >= terms.min_notional


def test_a_plan_the_check_passes_is_not_given_a_counter_under_the_minimum() -> None:
    """The reviewer's example: 1085-1544, 11 grids, 71.27 USDT, step 0.001."""
    terms = replace(_terms("0.001", "0.001"), max_notional_per_order=D(5000))
    evaluation = evaluate_grid(
        inputs(
            terms,
            D("1300"),
            lower="1085",
            upper="1544",
            grid_count="11",
            capital_quote="71.27",
            stop_loss="off",
            take_profit="off",
        ),
        GridThresholds(),
    )
    plan = evaluation.plan
    assert plan is not None
    for action in ladder_orders(opening_ladder(plan, terms)):
        _, counters = _counter_after_filling(plan, terms, action)
        assert all(c.quantity * c.price >= terms.min_notional for c in counters) or any(
            v.code == "LEVEL_BELOW_MIN_NOTIONAL" for v in evaluation.verdicts
        )
