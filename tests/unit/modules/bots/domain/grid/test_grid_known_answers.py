"""`EPIC-029C` — the report's example, as known answers (task §2's table)."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_evaluation import (
    GridEvaluation,
    evaluate_grid,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.report_example import (
    TERMS,
    inputs,
)


def _evaluate(**changes: str) -> GridEvaluation:
    evaluation = evaluate_grid(inputs(**changes), GridThresholds())
    assert evaluation.derived is not None
    return evaluation


def _pct(value: Decimal) -> Decimal:
    return (value * 100).quantize(Decimal("0.001"))


def test_arithmetic_step_is_1000() -> None:
    derived = _evaluate().derived
    assert derived is not None
    assert derived.step == Decimal(1000)
    assert derived.ratio is None


def test_net_profit_per_grid_bottom_and_top() -> None:
    derived = _evaluate().derived
    assert derived is not None
    assert _pct(derived.bottom.net_fraction) == Decimal("1.467")
    assert _pct(derived.top.net_fraction) == Decimal("1.249")
    assert derived.bottom.buy == Decimal(60000)
    assert derived.top.buy == Decimal(69000)


def test_geometric_ratio() -> None:
    derived = _evaluate(spacing="GEOMETRIC").derived
    assert derived is not None
    assert derived.ratio is not None
    assert derived.ratio.quantize(Decimal("0.00001")) == Decimal("1.01553")
    assert derived.step is None


def test_geometric_grids_all_earn_the_same_percentage() -> None:
    derived = _evaluate(spacing="GEOMETRIC").derived
    assert derived is not None
    nets = {_pct(grid.net_fraction) for grid in derived.grids}
    assert nets == {Decimal("1.353")}


def test_value_at_the_lower_limit_against_buy_and_hold() -> None:
    derived = _evaluate().derived
    assert derived is not None
    assert derived.at_lower.grid.quantize(Decimal(1)) == Decimal(9457)
    assert derived.at_lower.buy_and_hold.quantize(Decimal(1)) == Decimal(9231)


def test_value_at_the_upper_limit_against_buy_and_hold() -> None:
    """The report: above the range the bot trails buy-and-hold, +2.3% against +7.7%."""
    derived = _evaluate().derived
    assert derived is not None
    assert derived.at_upper.grid.quantize(Decimal(1)) == Decimal(10231)
    assert derived.at_upper.buy_and_hold.quantize(Decimal(1)) == Decimal(10769)


def test_cycles_to_recover_is_about_40() -> None:
    derived = _evaluate().derived
    assert derived is not None
    assert derived.cycles_to_recover is not None
    assert derived.cycles_to_recover.quantize(Decimal(1)) == Decimal(40)


def test_the_example_has_no_refusal_and_no_warning() -> None:
    evaluation = _evaluate()
    assert {v.severity.value for v in evaluation.verdicts} == {"OK"}


def test_value_at_lower_counts_the_cash_rounding_leaves() -> None:
    """With a 0.001 step the quantities round down and leave 292 USDT in cash:
    BUY 0.016, 0.016, 0.016, 0.015, 0.015 cost 4,833; SELL 5 × 0.015 cost 4,875;
    0.153 BTC at 60,000 is 9,180, plus 292 is 9,472."""
    evaluation = evaluate_grid(
        inputs(terms=replace(TERMS, step_size=Decimal("0.001"))), GridThresholds()
    )
    assert evaluation.derived is not None
    assert evaluation.derived.at_lower.grid == Decimal(9472)
    assert evaluation.derived.at_upper.grid == Decimal(5125) + Decimal("0.015") * 340000
