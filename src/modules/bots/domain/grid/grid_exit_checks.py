"""`EPIC-034F`, `EPIC-039I` — the verdicts on a Grid's exits: a stop loss or a take profit on the
wrong side of the range, and one too near or too far from it.

@details Split from `grid_checks.py`. The side is the direction's: a LONG (and Spot) grid's stop
loss sits under the range and its take profit over it; a SHORT grid's mirror that
(`GridParams.stop_loss_price`).
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.trade_direction import (
    TradeDirection,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_advice import plain
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_advice_texts import (
    SHORT_STOP_LOSS_SIDE,
    SHORT_TAKE_PROFIT_SIDE,
    STOP_LOSS_SIDE,
    TAKE_PROFIT_SIDE,
    ExitSide,
    exit_distance_advice,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_check_inputs import (
    GridCheckInputs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_checks import (
    OK,
    REFUSED,
    WARNING,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import Verdict


def check_stop_loss(inputs: GridCheckInputs) -> Verdict:
    params = inputs.params
    stop = params.stop_loss_price
    if stop is None:
        return Verdict(OK, "STOP_LOSS_OFF", "No stop loss is set")
    if params.direction is TradeDirection.SHORT:
        upper = params.upper
        if stop <= upper:
            return Verdict(
                REFUSED,
                "STOP_LOSS_INSIDE_RANGE",
                f"The stop loss {plain(stop)} is at or below the upper limit {plain(upper)}; put it "
                "above the range, where a short loses",
                {"stop_loss": stop, "upper": upper},
            )
        return _exit_distance(
            inputs, SHORT_STOP_LOSS_SIDE, stop, (stop - upper) / upper
        )
    lower = params.lower
    if stop >= lower:
        return Verdict(
            REFUSED,
            "STOP_LOSS_INSIDE_RANGE",
            f"The stop loss {plain(stop)} is at or above the lower limit {plain(lower)}; put it "
            "below the range",
            {"stop_loss": stop, "lower": lower},
        )
    return _exit_distance(inputs, STOP_LOSS_SIDE, stop, (lower - stop) / lower)


def check_take_profit(inputs: GridCheckInputs) -> Verdict:
    params = inputs.params
    target = params.take_profit_price
    if target is None:
        return Verdict(OK, "TAKE_PROFIT_OFF", "No take profit is set")
    if params.direction is TradeDirection.SHORT:
        lower = params.lower
        if target >= lower:
            return Verdict(
                REFUSED,
                "TAKE_PROFIT_INSIDE_RANGE",
                f"The take profit {plain(target)} is at or above the lower limit {plain(lower)}; put "
                "it below the range, where a short gains",
                {"take_profit": target, "lower": lower},
            )
        return _exit_distance(
            inputs, SHORT_TAKE_PROFIT_SIDE, target, (lower - target) / lower
        )
    upper = params.upper
    if target <= upper:
        return Verdict(
            REFUSED,
            "TAKE_PROFIT_INSIDE_RANGE",
            f"The take profit {plain(target)} is at or below the upper limit {plain(upper)}; put "
            "it above the range",
            {"take_profit": target, "upper": upper},
        )
    return _exit_distance(inputs, TAKE_PROFIT_SIDE, target, (target - upper) / upper)


def _exit_distance(
    inputs: GridCheckInputs, side: ExitSide, price: Decimal, distance: Decimal
) -> Verdict:
    code = side.name.upper().replace(" ", "_")
    low, high = (
        inputs.thresholds.exit_distance_low,
        inputs.thresholds.exit_distance_high,
    )
    numbers = {"distance": distance, "low": low, "high": high}
    if not low <= distance <= high:
        return Verdict(
            WARNING,
            f"{code}_DISTANCE",
            exit_distance_advice(inputs, side, price, distance).text,
            numbers,
        )
    return Verdict(OK, code, f"The {side.name} distance is within advice", numbers)
