"""`EPIC-039F` - the plan-time risk verdicts of a Futures Grid.

@details The business promise: a plan that can be liquidated before its ladder is used is
refused, the estimate is built on the worst-case position per direction with the bracket of
*that* notional, a leveraged plan needs an exit, and nothing is ever called safe."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_grid_checks import (
    FUTURES_PLAN_CODES,
    judge_futures_plan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_plan_risk_inputs import (
    PlanRiskInputs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_worst_case import (
    ladder_steps,
    worst_case_positions,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import (
    LevelSizing,
    plan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    FuturesGridThresholds,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import (
    Verdict,
    VerdictSeverity,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.futures_symbol_setting import (
    FuturesSymbolSetting,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_brackets import (
    LeverageBracket,
    LeverageBrackets,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.liquidation_estimate import (
    BracketedPosition,
    estimated_liquidation_price_in_brackets,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.report_example import (
    CONFIG,
    LAST_PRICE,
    TERMS,
)

D = Decimal
_BRACKETS = LeverageBrackets(
    "BTCUSDT",
    (
        LeverageBracket(1, 125, D(0), D(50_000), D("0.004"), D(0)),
        LeverageBracket(2, 100, D(50_000), D(250_000), D("0.005"), D(50)),
        LeverageBracket(3, 50, D(250_000), D(1_000_000), D("0.01"), D(1_300)),
    ),
)
_WIDE = FuturesGridThresholds(leverage_ceiling=125)
_ATR = D(2000)


def _inputs(
    direction: str = "LONG",
    leverage: int = 5,
    *,
    thresholds: FuturesGridThresholds = FuturesGridThresholds(),  # noqa: B008
    brackets: LeverageBrackets = _BRACKETS,
    margin_type: MarginType = MarginType.ISOLATED,
    atr: Decimal | None = _ATR,
    **changes: str,
) -> PlanRiskInputs:
    config = {
        **CONFIG,
        "direction": direction,
        "leverage": str(leverage),
        **changes,
    }
    params = GridParams.from_config(config)
    return PlanRiskInputs(
        params,
        plan(params, TERMS, LAST_PRICE, LevelSizing.EQUAL_QUANTITY),
        FuturesSymbolSetting("BTCUSDT", leverage, margin_type, D(10**9)),
        brackets,
        LAST_PRICE,
        thresholds,
        atr,
    )


def _codes(verdicts: tuple[Verdict, ...]) -> list[str]:
    return [v.code for v in verdicts]


def _severity(verdicts: tuple[Verdict, ...], code: str) -> VerdictSeverity:
    return next(v.severity for v in verdicts if v.code == code)


@pytest.mark.parametrize("direction", ["LONG", "SHORT"])
def test_a_plan_whose_liquidation_is_inside_the_range_is_refused(
    direction: str,
) -> None:
    verdicts = judge_futures_plan(_inputs(direction, 25, thresholds=_WIDE))

    assert _severity(verdicts, "LIQUIDATION_INSIDE_RANGE") is VerdictSeverity.REFUSED


def test_a_neutral_plan_is_judged_on_both_sides() -> None:
    verdicts = judge_futures_plan(_inputs("NEUTRAL", 80, thresholds=_WIDE))

    inside = [v for v in verdicts if v.code == "LIQUIDATION_INSIDE_RANGE"]
    assert len(inside) == 2
    assert {v.numbers["next_price"] > LAST_PRICE for v in inside} == {True, False}
    assert len(worst_case_positions(_inputs("NEUTRAL").plan)) == 2


def test_the_worst_case_is_the_far_edge_with_the_plans_average_entry() -> None:
    long_ = worst_case_positions(_inputs("LONG").plan)
    short = worst_case_positions(_inputs("SHORT").plan)

    assert len(long_) == len(short) == 1
    levels = _inputs("LONG").plan
    # LONG holds the opening quantity plus every BUY level at the lowest level.
    assert long_[0].quantity == levels.opening_quantity + sum(
        (lv.quantity for lv in levels.buy_levels), D(0)
    )
    assert LAST_PRICE > long_[0].average_entry > D(60000)
    assert D(70000) > short[0].average_entry > LAST_PRICE


def _binding_liquidation(
    inputs: PlanRiskInputs, brackets: LeverageBrackets = _BRACKETS
) -> list[Decimal]:
    """Each ladder step's liquidation price, in fill order."""
    prices = []
    for step in ladder_steps(inputs.plan, D(60000), D(70000)):
        position = step.position
        estimate = estimated_liquidation_price_in_brackets(
            BracketedPosition(
                position.side,
                position.quantity,
                position.average_entry,
                position.notional / inputs.params.leverage,
            ),
            brackets,
        ).price
        assert estimate is not None
        prices.append(estimate)
    return prices


def test_the_bracket_for_each_steps_own_notional_is_used_not_the_first() -> None:
    inputs = _inputs("LONG", 5, capital_quote="100000")
    ok = next(v for v in judge_futures_plan(inputs) if v.code == "LIQUIDATION_ESTIMATE")
    first_bracket_only = LeverageBrackets(
        "BTCUSDT", (replace(_BRACKETS.brackets[0], notional_cap=D(10**9)),)
    )

    worst = worst_case_positions(inputs.plan)[0]
    assert worst.notional > _BRACKETS.brackets[0].notional_cap
    right = _binding_liquidation(inputs)[-1]
    assert ok.numbers["liquidation_price"] == right
    assert right != _binding_liquidation(inputs, first_bracket_only)[-1]


def test_a_stop_loss_closer_than_one_atr_to_liquidation_warns() -> None:
    near = judge_futures_plan(_inputs("LONG", 5, atr=D(9000)))
    far = judge_futures_plan(_inputs("LONG", 5, atr=D(2000)))

    assert _severity(near, "STOP_LOSS_NEAR_LIQUIDATION") is VerdictSeverity.WARNING
    assert "STOP_LOSS_NEAR_LIQUIDATION" not in _codes(far)


def test_a_stop_loss_beyond_liquidation_is_refused() -> None:
    verdicts = judge_futures_plan(_inputs("LONG", 10))

    assert _severity(verdicts, "STOP_LOSS_AFTER_LIQUIDATION") is VerdictSeverity.REFUSED


def test_no_stop_loss_above_leverage_one_is_refused() -> None:
    verdicts = judge_futures_plan(_inputs("LONG", 5, stop_loss="off"))

    assert _severity(verdicts, "STOP_LOSS_NEEDED") is VerdictSeverity.REFUSED


def test_no_stop_loss_at_leverage_one_only_warns() -> None:
    verdicts = judge_futures_plan(_inputs("LONG", 1, stop_loss="off"))

    assert _severity(verdicts, "STOP_LOSS_NEEDED") is VerdictSeverity.WARNING


def test_a_short_is_judged_against_the_exit_above_the_range() -> None:
    verdicts = judge_futures_plan(_inputs("SHORT", 5, stop_loss="off"))

    assert _severity(verdicts, "STOP_LOSS_NEEDED") is VerdictSeverity.REFUSED


def test_the_ok_verdict_says_estimate() -> None:
    (verdict,) = judge_futures_plan(_inputs("LONG", 5))

    assert verdict.severity is VerdictSeverity.OK
    assert "estimate" in verdict.reason
    assert "safe" not in verdict.reason.lower()
    assert verdict.numbers["liquidation_price"] < D(57000)


def test_a_cross_margin_symbol_is_refused() -> None:
    verdicts = judge_futures_plan(_inputs(margin_type=MarginType.CROSSED))

    assert _severity(verdicts, "CROSS_MARGIN_UNSUPPORTED") is VerdictSeverity.REFUSED


def test_leverage_above_the_warning_warns_and_above_the_ceiling_is_refused() -> None:
    thresholds = FuturesGridThresholds(leverage_warn=4, leverage_ceiling=6)

    assert (
        _severity(
            judge_futures_plan(_inputs(leverage=5, thresholds=thresholds)),
            "LEVERAGE_HIGH",
        )
        is VerdictSeverity.WARNING
    )
    assert (
        _severity(
            judge_futures_plan(_inputs(leverage=7, thresholds=thresholds)),
            "LEVERAGE_ABOVE_CEILING",
        )
        is VerdictSeverity.REFUSED
    )


def test_a_notional_above_what_the_symbol_allows_at_that_leverage_is_refused() -> None:
    small = LeverageBrackets(
        "BTCUSDT", (LeverageBracket(1, 125, D(0), D(20_000), D("0.004"), D(0)),)
    )

    verdicts = judge_futures_plan(_inputs("LONG", 5, brackets=small))

    assert _severity(verdicts, "NOTIONAL_ABOVE_BRACKET") is VerdictSeverity.REFUSED


def test_more_initial_margin_than_the_bot_commits_is_refused() -> None:
    inputs = _inputs("LONG", 5)
    starved = replace(inputs, params=replace(inputs.params, capital_quote=D(100)))

    assert (
        _severity(judge_futures_plan(starved), "MARGIN_TOO_SMALL")
        is VerdictSeverity.REFUSED
    )


def test_a_plan_with_a_sound_stop_and_margin_is_only_estimated() -> None:
    verdicts = judge_futures_plan(_inputs("LONG", 5))

    assert not any(v.refuses for v in verdicts)
    assert _codes(verdicts) == ["LIQUIDATION_ESTIMATE"]


def test_the_thresholds_refuse_inverted_liquidation_distances() -> None:
    with pytest.raises(ValueError, match="critical < warn"):
        FuturesGridThresholds(
            liq_warn_distance=D("0.02"), liq_critical_distance=D("0.05")
        )


@pytest.mark.parametrize("direction", ["LONG", "SHORT"])
def test_a_plan_liquidated_between_two_levels_is_refused_though_the_far_edge_looks_fine(
    direction: str,
) -> None:
    """Review of PR #486: at 16x a long holding the levels down to 61,000 is liquidated at
    about 60,172, before the 60,000 level fills; judging only the far edge missed it."""
    inputs = _inputs(direction, 16, stop_loss="price:59990", take_profit="price:70010")

    verdicts = judge_futures_plan(inputs)

    inside = next(v for v in verdicts if v.code == "LIQUIDATION_INSIDE_RANGE")
    assert inside.severity is VerdictSeverity.REFUSED
    assert "between" in inside.reason


def test_every_step_of_the_ladder_is_estimated_with_its_own_position_and_entry() -> (
    None
):
    steps = ladder_steps(_inputs("LONG").plan, D(60000), D(70000))

    quantities = [s.position.quantity for s in steps]
    assert quantities == sorted(quantities)  # the position only grows on the way down
    assert [s.next_price for s in steps][-1] == D(60000)  # after the last BUY: the edge
    assert steps[0].next_price == D(
        64000
    )  # the opening position waits for the first BUY


def test_the_exit_is_judged_against_the_full_positions_liquidation_not_an_earlier_step() -> (
    None
):
    """Review of PR #486, round two: the price reaches the exit only after every level has
    filled, so the exit is compared with the last step's liquidation (51,004 at 5x), not with
    the smaller opening position's (52,209), which a sound exit at 51,304 sits below."""
    inputs = _inputs("LONG", 5, stop_loss="price:51304", atr=None)

    verdicts = judge_futures_plan(inputs)

    assert not any(v.refuses for v in verdicts)
    (ok,) = verdicts
    assert ok.numbers["liquidation_price"] == _binding_liquidation(inputs)[-1]


def test_a_side_verdict_names_its_side_so_a_neutral_plan_can_tell_two_estimates_apart() -> (
    None
):
    verdicts = judge_futures_plan(_inputs("NEUTRAL", 3))

    estimates = {v.subject for v in verdicts if v.code == "LIQUIDATION_ESTIMATE"}
    assert estimates == {"long", "short"}


def test_the_estimate_carries_the_exit_and_its_distance_when_the_plan_has_one() -> None:
    (verdict,) = judge_futures_plan(_inputs("LONG", 5))

    assert verdict.numbers["exit_price"] == D(57000)
    assert verdict.numbers["gap"] == D(57000) - verdict.numbers["liquidation_price"]


def test_a_stop_close_to_liquidation_carries_the_price_it_measured_against() -> None:
    near = judge_futures_plan(_inputs("LONG", 5, atr=D(9000)))

    (warning,) = [v for v in near if v.code == "STOP_LOSS_NEAR_LIQUIDATION"]
    assert warning.numbers["liquidation_price"] < warning.numbers["exit_price"]


@pytest.mark.parametrize(
    "plan",
    [
        _inputs("LONG", 5),
        _inputs("SHORT", 5, take_profit="off"),
        _inputs("NEUTRAL", 80, thresholds=_WIDE),
        _inputs("LONG", 30),
        _inputs(margin_type=MarginType.CROSSED),
    ],
)
def test_every_code_the_guard_returns_is_one_the_screen_has_placed(
    plan: PlanRiskInputs,
) -> None:
    assert {v.code for v in judge_futures_plan(plan)} <= FUTURES_PLAN_CODES
