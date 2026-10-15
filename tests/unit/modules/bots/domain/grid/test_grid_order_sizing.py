"""`BUG-212` - the pre-start judgement and the executor size the Grid's orders the same way.

The owner's Spot MAINNET start (ETHUSDT, 2348-2667, 7 grids, 35 USDT, price 2363.77): the
check judged each level's notional less the fee, the executor floors the SELL quantity to the
step after the fee, so the check passed an order of 4.79 USDT that Binance refuses under its
5 USDT minimum - after the opening market buy was already spent. Both now size through
`grid_order_sizing`, which these tests hold to the exchange's filters.
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
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_order_sizing import (
    OrderOrigin,
    find_breach,
    opening_ladder,
    sized_orders,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import VerdictSeverity
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.report_example import (
    inputs,
)

D = Decimal
_ETHUSDT = ExchangeTerms(
    tick_size=D("0.01"),
    step_size=D("0.0001"),
    min_notional=D(5),
    maker_fee=D("0.001"),
    taker_fee=D("0.001"),
    max_notional_per_order=D(5000),
    max_open_orders=100,
)
_OWNER = {
    "lower": "2348",
    "upper": "2667",
    "grid_count": "7",
    "capital_quote": "35",
    "stop_loss": "price:2259",
    "take_profit": "price:2805",
}


def _owner_evaluation(**changes: str):
    return evaluate_grid(
        inputs(_ETHUSDT, D("2363.77"), **{**_OWNER, **changes}), GridThresholds()
    )


def test_the_owners_plan_is_refused_before_start_naming_the_order_and_the_minimum() -> (
    None
):
    evaluation = _owner_evaluation()

    refused = [v for v in evaluation.verdicts if v.refuses]
    below = [v for v in refused if v.code == "LEVEL_BELOW_MIN_NOTIONAL"]
    assert len(below) == 1
    assert below[0].severity is VerdictSeverity.REFUSED
    assert "L1 SELL" in below[0].reason
    assert "0.0020" in below[0].reason
    assert "is worth 4.79" in below[0].reason
    assert "minimum of 5" in below[0].reason
    assert "fewer grids" in below[0].reason


def test_the_capital_the_refusal_names_is_one_that_passes() -> None:
    needed = _owner_evaluation().verdicts
    named = next(v for v in needed if v.code == "LEVEL_BELOW_MIN_NOTIONAL")
    capital = named.numbers["minimum_capital"]

    retried = _owner_evaluation(capital_quote=str(capital))

    assert not [v for v in retried.verdicts if v.code == "LEVEL_BELOW_MIN_NOTIONAL"]


def test_the_check_judges_the_quantities_the_executor_sends() -> None:
    """The executor lays `opening_ladder`; the refused order is one of its orders."""
    evaluation = _owner_evaluation()
    assert evaluation.plan is not None and evaluation.params is not None

    laid = ladder_orders(opening_ladder(evaluation.plan, _ETHUSDT))
    breach = find_breach(evaluation.params, evaluation.plan, _ETHUSDT)

    assert breach is not None
    assert any(
        (a.level_index, a.side, a.quantity)
        == (breach.order.level_index, breach.order.side, breach.order.quantity)
        for a in laid
    )
    assert breach.order.notional < _ETHUSDT.min_notional


@pytest.mark.parametrize("capital", ["35", "60", "100", "250", "1000"])
@pytest.mark.parametrize("grids", [3, 7, 12])
@pytest.mark.parametrize("price", ["2300", "2363.77", "2500", "2700"])
def test_a_plan_the_check_passes_sends_only_orders_the_exchange_accepts(
    capital: str, grids: int, price: str
) -> None:
    evaluation = evaluate_grid(
        inputs(
            _ETHUSDT,
            D(price),
            **{**_OWNER, "capital_quote": capital, "grid_count": str(grids)},
        ),
        GridThresholds(),
    )
    if evaluation.plan is None or any(
        v.code == "LEVEL_BELOW_MIN_NOTIONAL" for v in evaluation.verdicts
    ):
        assert evaluation.params is not None
        assert evaluation.plan is not None
        assert find_breach(evaluation.params, evaluation.plan, _ETHUSDT) is not None
        return

    for order in sized_orders(evaluation.plan, _ETHUSDT):
        assert order.quantity > 0
        assert order.notional >= _ETHUSDT.min_notional
        assert order.quantity % _ETHUSDT.step_size == 0
    for action in ladder_orders(opening_ladder(evaluation.plan, _ETHUSDT)):
        assert action.quantity * action.price >= _ETHUSDT.min_notional


def test_a_passing_plan_has_no_breach_and_counters_are_sized_too() -> None:
    evaluation = _owner_evaluation(capital_quote="100")
    assert evaluation.plan is not None and evaluation.params is not None

    assert find_breach(evaluation.params, evaluation.plan, _ETHUSDT) is None
    origins = {o.origin for o in sized_orders(evaluation.plan, _ETHUSDT)}
    assert origins == {OrderOrigin.START, OrderOrigin.COUNTER}


def test_a_quantity_that_rounds_to_nothing_is_a_breach_not_a_skipped_order() -> None:
    coarse = replace(_ETHUSDT, step_size=D(1))
    evaluation = _owner_evaluation()
    assert evaluation.plan is not None and evaluation.params is not None

    breach = find_breach(evaluation.params, evaluation.plan, coarse)

    assert breach is not None
    assert breach.order.quantity == 0
