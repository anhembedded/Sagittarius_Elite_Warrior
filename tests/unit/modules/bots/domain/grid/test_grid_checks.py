"""`EPIC-029C` — every check at its boundary: at the threshold and one step either side."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_evaluation import (
    GridEvaluation,
    evaluate_grid,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import (
    Verdict,
    VerdictSeverity,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.report_example import (
    TERMS,
    inputs,
)

OK = VerdictSeverity.OK
WARNING = VerdictSeverity.WARNING
REFUSED = VerdictSeverity.REFUSED
CENT = Decimal("0.01")


def _verdict(evaluation: GridEvaluation, *codes: str) -> Verdict:
    matches = [v for v in evaluation.verdicts if v.code in codes]
    assert len(matches) == 1, evaluation.verdicts
    return matches[0]


def _evaluate(
    thresholds: GridThresholds | None = None, **kwargs: object
) -> GridEvaluation:
    return evaluate_grid(inputs(**kwargs), thresholds or GridThresholds())


# --- break even (REFUSED when every grid loses) -----------------------------

_ONE_GRID = {"lower": "100", "grid_count": "1", "capital_quote": "1000"}


def test_a_step_exactly_two_maker_fees_refuses() -> None:
    evaluation = _evaluate(last_price=Decimal("100.1"), upper="100.2", **_ONE_GRID)
    verdict = _verdict(evaluation, "EVERY_CYCLE_LOSES", "SOME_GRIDS_LOSE", "BREAK_EVEN")
    assert verdict.code == "EVERY_CYCLE_LOSES"
    assert verdict.refuses
    assert verdict.numbers["widest_step"] == Decimal("0.002")


def test_a_step_one_tick_above_two_maker_fees_passes() -> None:
    evaluation = _evaluate(last_price=Decimal("100.1"), upper="100.21", **_ONE_GRID)
    verdict = _verdict(evaluation, "EVERY_CYCLE_LOSES", "SOME_GRIDS_LOSE", "BREAK_EVEN")
    assert verdict.code == "BREAK_EVEN"


def test_a_step_one_tick_below_two_maker_fees_refuses() -> None:
    evaluation = _evaluate(last_price=Decimal("100.1"), upper="100.19", **_ONE_GRID)
    assert _verdict(evaluation, "EVERY_CYCLE_LOSES", "BREAK_EVEN").refuses


def test_thin_upper_grids_only_warn() -> None:
    """Arithmetic over 100–200 in 400 grids: 0.25% at the bottom, 0.125% at the top."""
    evaluation = _evaluate(
        terms=replace(TERMS, max_open_orders=1000),
        last_price=Decimal(150),
        lower="100",
        upper="200",
        grid_count="400",
        capital_quote="400000",
        stop_loss="off",
        take_profit="off",
    )
    verdict = _verdict(evaluation, "EVERY_CYCLE_LOSES", "SOME_GRIDS_LOSE", "BREAK_EVEN")
    assert verdict.code == "SOME_GRIDS_LOSE"
    assert verdict.severity is WARNING
    assert Decimal(0) < verdict.numbers["losing_grids"] < Decimal(400)


# --- min and max notional (REFUSED) ---------------------------------------


def _smallest_and_largest_order() -> tuple[Decimal, Decimal]:
    plan = _evaluate().plan
    assert plan is not None
    notionals = [level.notional for level in plan.order_levels]
    return min(notionals), max(notionals)


def test_min_notional_at_the_smallest_order_passes_and_a_cent_more_refuses() -> None:
    smallest, _ = _smallest_and_largest_order()
    at = _evaluate(terms=replace(TERMS, min_notional=smallest))
    above = _evaluate(terms=replace(TERMS, min_notional=smallest + CENT))
    assert _verdict(at, "MIN_NOTIONAL", "LEVEL_BELOW_MIN_NOTIONAL").severity is OK
    refused = _verdict(above, "MIN_NOTIONAL", "LEVEL_BELOW_MIN_NOTIONAL")
    assert refused.code == "LEVEL_BELOW_MIN_NOTIONAL"
    assert refused.refuses
    assert refused.numbers["smallest_order"] == smallest


def test_cap_at_the_largest_order_passes_and_a_cent_less_refuses_naming_the_cap() -> (
    None
):
    _, largest = _smallest_and_largest_order()
    at = _evaluate(terms=replace(TERMS, max_notional_per_order=largest))
    below = _evaluate(terms=replace(TERMS, max_notional_per_order=largest - CENT))
    assert _verdict(at, "MAX_NOTIONAL", "LEVEL_ABOVE_MAX_NOTIONAL").severity is OK
    refused = _verdict(below, "MAX_NOTIONAL", "LEVEL_ABOVE_MAX_NOTIONAL")
    assert refused.code == "LEVEL_ABOVE_MAX_NOTIONAL"
    assert refused.numbers["cap"] == largest - CENT
    assert str(largest - CENT) in refused.reason


@pytest.mark.parametrize("cap", [Decimal(500), Decimal(1000), Decimal("1076.5")])
def test_the_suggested_largest_capital_passes_and_a_dollar_more_does_not(
    cap: Decimal,
) -> None:
    """PR #318 review: a SELL level is worth `capital × price / last_price`, more
    than its capital, so `cap × levels` was itself refused. The suggestion must
    round-trip to OK, and be the largest such capital to the dollar."""
    terms = replace(TERMS, max_notional_per_order=cap)
    refused = _verdict(
        _evaluate(terms=terms), "MAX_NOTIONAL", "LEVEL_ABOVE_MAX_NOTIONAL"
    )
    assert refused.code == "LEVEL_ABOVE_MAX_NOTIONAL"
    suggested = refused.numbers["largest_capital"]
    at = _evaluate(terms=terms, capital_quote=str(suggested))
    above = _evaluate(terms=terms, capital_quote=str(suggested + 1))
    assert (
        _verdict(at, "MAX_NOTIONAL", "LEVEL_ABOVE_MAX_NOTIONAL").code == "MAX_NOTIONAL"
    )
    assert _verdict(above, "MAX_NOTIONAL", "LEVEL_ABOVE_MAX_NOTIONAL").refuses


def test_the_largest_capital_is_bound_by_the_highest_sell_level() -> None:
    """Cap 1,000 over 10 orders, the 70,000 SELL bought at 65,000: 10,000 × 65/70."""
    terms = replace(TERMS, max_notional_per_order=Decimal(1000))
    refused = _verdict(_evaluate(terms=terms), "LEVEL_ABOVE_MAX_NOTIONAL")
    assert refused.numbers["largest_capital"] == Decimal("9285.71")


def test_more_grids_than_may_be_open_is_refused_before_any_plan() -> None:
    evaluation = _evaluate(grid_count="200000")
    assert [v.code for v in evaluation.verdicts] == ["TOO_MANY_LEVELS"]
    assert evaluation.verdicts[0].refuses
    assert evaluation.plan is None


@pytest.mark.parametrize(
    ("last_price", "grid_count", "code"),
    [
        (Decimal(65000), "100", "OPEN_ORDERS"),  # one level EMPTY: 100 orders
        (Decimal(50000), "100", "TOO_MANY_LEVELS"),  # outside the range: 101
        (Decimal(50000), "99", "OPEN_ORDERS"),  # outside the range: 100
    ],
)
def test_the_exact_order_count_meets_the_open_order_limit(
    last_price: Decimal, grid_count: str, code: str
) -> None:
    evaluation = _evaluate(
        last_price=last_price, grid_count=grid_count, capital_quote="1000000"
    )
    assert _verdict(evaluation, "OPEN_ORDERS", "TOO_MANY_LEVELS").code == code


def test_the_four_refusals_are_the_only_refusals() -> None:
    codes = {
        v.code
        for kwargs in (
            {"terms": replace(TERMS, min_notional=Decimal(10**9))},
            {"terms": replace(TERMS, max_notional_per_order=Decimal(1))},
            {"last_price": Decimal("100.1"), "upper": "100.2", **_ONE_GRID},
            {
                "stop_loss": "price:65000",
                "take_profit": "price:65000",
                "grid_count": "1000",
            },
            {"grid_count": "101"},
            {"last_price": Decimal(50000), "grid_count": "100"},
        )
        for v in _evaluate(**kwargs).verdicts
        if v.refuses
    }
    assert codes <= {
        "EVERY_CYCLE_LOSES",
        "LEVEL_BELOW_MIN_NOTIONAL",
        "LEVEL_ABOVE_MAX_NOTIONAL",
        "TOO_MANY_LEVELS",
    }


# --- warnings ---------------------------------------------------------------


def test_min_step_threshold_at_the_thinnest_step_passes_and_just_above_warns() -> None:
    derived = _evaluate().derived
    assert derived is not None
    thinnest = derived.smallest_step_fraction
    at = _evaluate(GridThresholds(min_step_fraction=thinnest))
    above = _evaluate(GridThresholds(min_step_fraction=thinnest + Decimal("1e-12")))
    assert _verdict(at, "STEP_SIZE", "STEP_BELOW_MINIMUM").severity is OK
    warned = _verdict(above, "STEP_SIZE", "STEP_BELOW_MINIMUM")
    assert warned.code == "STEP_BELOW_MINIMUM"
    assert warned.numbers["thinnest_step"] == thinnest


@pytest.mark.parametrize(
    ("daily_atr", "code"),
    [
        (Decimal(5000), "RANGE_ATR"),  # exactly 2 ATRs
        (Decimal("5000.01"), "RANGE_OUTSIDE_ATR_BAND"),  # just under 2
        (Decimal(2500), "RANGE_ATR"),  # exactly 4 ATRs
        (Decimal("2499.99"), "RANGE_OUTSIDE_ATR_BAND"),  # just over 4
        (None, "RANGE_ATR_NOT_CHECKED"),
    ],
)
def test_range_against_daily_atr(daily_atr: Decimal | None, code: str) -> None:
    evaluation = _evaluate(daily_atr=daily_atr)
    verdict = _verdict(
        evaluation, "RANGE_ATR", "RANGE_OUTSIDE_ATR_BAND", "RANGE_ATR_NOT_CHECKED"
    )
    assert verdict.code == code
    assert verdict.severity is (WARNING if code == "RANGE_OUTSIDE_ATR_BAND" else OK)


@pytest.mark.parametrize(
    ("stop_loss", "code"),
    [
        ("percent:3", "STOP_LOSS"),
        ("percent:8", "STOP_LOSS"),
        ("percent:2.99", "STOP_LOSS_DISTANCE"),
        ("percent:8.01", "STOP_LOSS_DISTANCE"),
        ("price:60000", "STOP_LOSS_INSIDE_RANGE"),
        ("price:59999.99", "STOP_LOSS_DISTANCE"),
        ("off", "STOP_LOSS_OFF"),
    ],
)
def test_stop_loss(stop_loss: str, code: str) -> None:
    verdict = _verdict(
        _evaluate(stop_loss=stop_loss),
        "STOP_LOSS",
        "STOP_LOSS_DISTANCE",
        "STOP_LOSS_INSIDE_RANGE",
        "STOP_LOSS_OFF",
    )
    assert verdict.code == code
    assert verdict.severity is (
        OK if code in {"STOP_LOSS", "STOP_LOSS_OFF"} else WARNING
    )


@pytest.mark.parametrize(
    ("take_profit", "code"),
    [
        ("percent:3", "TAKE_PROFIT"),
        ("percent:8", "TAKE_PROFIT"),
        ("percent:2.99", "TAKE_PROFIT_DISTANCE"),
        ("percent:8.01", "TAKE_PROFIT_DISTANCE"),
        ("price:70000", "TAKE_PROFIT_INSIDE_RANGE"),
        ("price:70000.01", "TAKE_PROFIT_DISTANCE"),
        ("off", "TAKE_PROFIT_OFF"),
    ],
)
def test_take_profit(take_profit: str, code: str) -> None:
    verdict = _verdict(
        _evaluate(take_profit=take_profit),
        "TAKE_PROFIT",
        "TAKE_PROFIT_DISTANCE",
        "TAKE_PROFIT_INSIDE_RANGE",
        "TAKE_PROFIT_OFF",
    )
    assert verdict.code == code
    assert verdict.severity is (
        OK if code in {"TAKE_PROFIT", "TAKE_PROFIT_OFF"} else WARNING
    )


def test_a_stop_loss_distance_warning_carries_the_measured_value() -> None:
    verdict = _verdict(_evaluate(stop_loss="percent:10"), "STOP_LOSS_DISTANCE")
    assert verdict.numbers["distance"] == Decimal("0.1")
    assert verdict.numbers["low"] == Decimal("0.03")
    assert verdict.numbers["high"] == Decimal("0.08")


@pytest.mark.parametrize(
    ("spacing", "upper", "code"),
    [
        ("ARITHMETIC", "72000", "SPACING"),  # exactly 20%
        ("ARITHMETIC", "72000.01", "ARITHMETIC_ON_WIDE_RANGE"),
        ("GEOMETRIC", "90000", "SPACING"),
    ],
)
def test_arithmetic_on_a_wide_range(spacing: str, upper: str, code: str) -> None:
    evaluation = _evaluate(spacing=spacing, upper=upper, take_profit="off")
    assert _verdict(evaluation, "SPACING", "ARITHMETIC_ON_WIDE_RANGE").code == code


def test_thresholds_are_the_reports_defaults() -> None:
    defaults = GridThresholds()
    assert defaults.min_step_fraction == Decimal("0.005")
    assert (defaults.range_atr_low, defaults.range_atr_high) == (Decimal(2), Decimal(4))
    assert (defaults.exit_distance_low, defaults.exit_distance_high) == (
        Decimal("0.03"),
        Decimal("0.08"),
    )
    assert defaults.arithmetic_max_range_fraction == Decimal("0.20")


# --- unreadable parameters --------------------------------------------------


@pytest.mark.parametrize(
    "changes",
    [
        {"lower": "abc"},
        {"upper": "59000"},
        {"grid_count": "0"},
        {"grid_count": "2.5"},
        {"spacing": "LOG"},
        {"stop_loss": "percent"},
        {"stop_loss": "percent:-1"},
        {"take_profit": "ticks:5"},
        {"capital_quote": "NaN"},
        {"grid_count": "²"},
        {"upper": "1e999999999"},
        {"stop_loss": "percent:1e999999999"},
        {"take_profit": "percent:1e999999999"},
        {"stop_loss": "percent:100"},
    ],
)
def test_unreadable_parameters_are_one_refusal_and_no_plan(
    changes: dict[str, str],
) -> None:
    evaluation = _evaluate(**changes)
    assert [v.code for v in evaluation.verdicts] == ["PARAMETERS_UNREADABLE"]
    assert evaluation.verdicts[0].refuses
    assert evaluation.plan is None


def test_a_grid_exactly_at_two_maker_fees_counts_as_losing() -> None:
    """Two grids, 99.8–100–100.2: the upper step is exactly 0.2%, the lower just above."""
    evaluation = _evaluate(
        last_price=Decimal(100),
        lower="99.8",
        upper="100.2",
        grid_count="2",
        capital_quote="100",
        stop_loss="off",
        take_profit="off",
    )
    verdict = _verdict(evaluation, "EVERY_CYCLE_LOSES", "SOME_GRIDS_LOSE", "BREAK_EVEN")
    assert verdict.numbers["thinnest_step"] == Decimal("0.002")
    assert verdict.code == "SOME_GRIDS_LOSE"
    assert verdict.numbers["losing_grids"] == Decimal(1)


def test_a_zero_atr_is_treated_as_no_candles() -> None:
    verdict = _verdict(_evaluate(daily_atr=Decimal(0)), "RANGE_ATR_NOT_CHECKED")
    assert verdict.severity is OK


def test_an_extreme_market_value_is_unreadable_not_a_crash() -> None:
    """PR #318 review round 2: the checks ran outside the arithmetic guard."""
    evaluation = _evaluate(daily_atr=Decimal("1e-999999999"))
    assert [v.code for v in evaluation.verdicts] == ["PARAMETERS_UNREADABLE"]
