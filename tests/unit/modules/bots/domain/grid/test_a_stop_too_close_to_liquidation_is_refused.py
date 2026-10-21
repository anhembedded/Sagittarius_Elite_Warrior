"""`BUG-255` - a stop loss too close to the estimated liquidation is refused, with or without an ATR.

@details The Start passes no daily ATR, so the advisory buffer (`STOP_LOSS_NEAR_LIQUIDATION`) never
spoke at Start and a WARNING never refuses. The floor is a share of the exit's price: it needs no
ATR and is judged by the one function the Plan and the Start both call.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_grid_checks import (
    judge_futures_plan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_plan_risk_inputs import (
    PlanRiskInputs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    FuturesGridThresholds,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import (
    VerdictSeverity,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.test_futures_grid_checks import (
    _ATR,
    _codes,
    _inputs,
    _severity,
)

D = Decimal


def _liquidation_of(inputs: PlanRiskInputs) -> Decimal:
    ok = next(v for v in judge_futures_plan(inputs) if v.code == "LIQUIDATION_ESTIMATE")
    return ok.numbers["liquidation_price"]


def _stop_above_liquidation_by(ratio: Decimal, atr: Decimal | None) -> PlanRiskInputs:
    """A LONG whose stop sits `ratio` of the stop's price above the estimated liquidation."""
    liquidation = _liquidation_of(_inputs("LONG", 5, atr=atr))
    stop = (liquidation / (1 - ratio)).quantize(D("0.01"))
    return _inputs("LONG", 5, atr=atr, stop_loss=f"price:{stop}")


@pytest.mark.parametrize("atr", [None, _ATR], ids=["no-atr", "atr"])
def test_a_stop_closer_to_liquidation_than_the_floor_is_refused_with_or_without_an_atr(
    atr: Decimal | None,
) -> None:
    """`BUG-255`: the start passes no daily ATR, so a stop 1.51 before the estimate (0.23% of the
    exit) only ever warned in the Plan and passed `plan risk OK` at Start. The floor needs no ATR,
    so the Plan and the Start judge it alike."""
    floor = FuturesGridThresholds().min_liq_gap_ratio
    inside = _stop_above_liquidation_by(floor / 2, atr)
    outside = _stop_above_liquidation_by(floor * 2, atr)

    refused = judge_futures_plan(inside)
    assert _severity(refused, "STOP_LOSS_TOO_CLOSE_TO_LIQUIDATION") is (
        VerdictSeverity.REFUSED
    )
    assert "STOP_LOSS_TOO_CLOSE_TO_LIQUIDATION" not in _codes(
        judge_futures_plan(outside)
    )


def test_the_floor_is_the_thresholds_not_a_literal() -> None:
    wide = FuturesGridThresholds(min_liq_gap_ratio=D("0.2"))
    far_enough_by_default = _stop_above_liquidation_by(D("0.05"), None)

    assert "STOP_LOSS_TOO_CLOSE_TO_LIQUIDATION" not in _codes(
        judge_futures_plan(far_enough_by_default)
    )
    assert "STOP_LOSS_TOO_CLOSE_TO_LIQUIDATION" in _codes(
        judge_futures_plan(replace(far_enough_by_default, thresholds=wide))
    )


def test_a_negative_floor_is_not_a_threshold() -> None:
    with pytest.raises(ValueError, match="min_liq_gap_ratio"):
        FuturesGridThresholds(min_liq_gap_ratio=D("-0.01"))
