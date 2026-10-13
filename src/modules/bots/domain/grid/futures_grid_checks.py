"""`EPIC-039F` - the plan-time risk verdicts of a Futures Grid (DESIGN §6).

@details Each check answers a `Verdict`; `judge_futures_plan` returns them in a fixed order.
They are pure over `PlanRiskInputs`; the numbers are `FuturesGridThresholds`', never literals.

  · `CROSS_MARGIN_UNSUPPORTED` (REFUSED): the estimate sees one position and is optimistic
    under Cross; this epic offers Isolated only (O5).
  · `LEVERAGE_ABOVE_CEILING` (REFUSED) and `LEVERAGE_HIGH` (WARNING) - O4.
  · `NOTIONAL_ABOVE_BRACKET` (REFUSED): the worst-case notional exceeds the largest notional
    the symbol allows at the chosen leverage.
  · `MARGIN_TOO_SMALL` (REFUSED): the worst case needs more initial margin than the capital
    the user committed.
  · per exposed side, with the liquidation price estimated for the worst-case position
    (`futures_worst_case.py`, the bracket looked up for *its* notional):
    `LIQUIDATION_INSIDE_RANGE` (REFUSED), `STOP_LOSS_NEEDED` (REFUSED above leverage 1,
    WARNING at 1 - O3), `STOP_LOSS_AFTER_LIQUIDATION` (REFUSED), `STOP_LOSS_NEAR_LIQUIDATION`
    (WARNING, closer than `min_liq_buffer_atr` daily ATRs); when none objects, one OK verdict
    that says *estimate*.

The exit on a side is the exit that closes that side at a loss: a LONG's is the stop loss
(below the range), a SHORT's is the exit above the range (`take_profit` in the parameters).
The guard never says "safe" and never changes a parameter.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_plan_risk_inputs import (
    PlanRiskInputs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_worst_case import (
    LadderStep,
    ladder_steps,
    worst_case_positions,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import (
    Verdict,
    VerdictSeverity,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.liquidation_estimate import (
    BracketedPosition,
    estimated_liquidation_price_in_brackets,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.position_side import (
    PositionSide,
)

_OK, _WARNING, _REFUSED = (
    VerdictSeverity.OK,
    VerdictSeverity.WARNING,
    VerdictSeverity.REFUSED,
)


def judge_futures_plan(inputs: PlanRiskInputs) -> tuple[Verdict, ...]:
    """Every risk verdict the plan earns, in a fixed order; `()` when none objects and the
    plan has no exposed side to estimate."""
    found = [
        *_margin_mode(inputs),
        *_leverage(inputs),
        *_bracket_and_margin(inputs),
    ]
    steps = ladder_steps(inputs.plan, inputs.params.lower, inputs.params.upper)
    for side in (PositionSide.LONG, PositionSide.SHORT):
        side_steps = [step for step in steps if step.position.side is side]
        if side_steps:
            found.extend(_side(inputs, side, side_steps))
    return tuple(found)


def _margin_mode(inputs: PlanRiskInputs) -> list[Verdict]:
    if inputs.setting.margin_type is MarginType.ISOLATED:
        return []
    return [
        Verdict(
            _REFUSED,
            "CROSS_MARGIN_UNSUPPORTED",
            f"{inputs.setting.symbol} is on {inputs.setting.margin_type.name.lower()} "
            "margin; the liquidation estimate is optimistic there, so a bot runs on "
            "isolated margin only",
        )
    ]


def _leverage(inputs: PlanRiskInputs) -> list[Verdict]:
    leverage, thresholds = inputs.params.leverage, inputs.thresholds
    numbers = {
        "leverage": Decimal(leverage),
        "warn": Decimal(thresholds.leverage_warn),
        "ceiling": Decimal(thresholds.leverage_ceiling),
    }
    if leverage > thresholds.leverage_ceiling:
        return [
            Verdict(
                _REFUSED,
                "LEVERAGE_ABOVE_CEILING",
                f"{leverage}x is above the {thresholds.leverage_ceiling}x ceiling",
                numbers,
            )
        ]
    if leverage > thresholds.leverage_warn:
        return [
            Verdict(
                _WARNING,
                "LEVERAGE_HIGH",
                f"{leverage}x is above {thresholds.leverage_warn}x: a small move "
                "against the position liquidates it",
                numbers,
            )
        ]
    return []


def _bracket_and_margin(inputs: PlanRiskInputs) -> list[Verdict]:
    positions = worst_case_positions(inputs.plan)
    if not positions:
        return []
    leverage = inputs.params.leverage
    notional = max(position.notional for position in positions)
    allowed = max(
        (
            b.notional_cap
            for b in inputs.brackets.brackets
            if b.initial_leverage >= leverage
        ),
        default=Decimal(0),
    )
    found: list[Verdict] = []
    if notional > allowed:
        found.append(
            Verdict(
                _REFUSED,
                "NOTIONAL_ABOVE_BRACKET",
                f"The ladder can reach a position worth {notional:.2f}; "
                f"{inputs.setting.symbol} allows at most {allowed:.2f} at {leverage}x",
                {"worst_case_notional": notional, "allowed_notional": allowed},
            )
        )
    margin = notional / leverage
    committed = inputs.params.capital_quote
    if margin > committed:
        found.append(
            Verdict(
                _REFUSED,
                "MARGIN_TOO_SMALL",
                f"The worst case needs {margin:.2f} of initial margin and the bot "
                f"commits {committed:.2f}",
                {"initial_margin": margin, "committed": committed},
            )
        )
    return found


def _side(
    inputs: PlanRiskInputs, side: PositionSide, steps: list[LadderStep]
) -> list[Verdict]:
    estimates = [(step, _estimate(inputs, step)) for step in steps]
    # The price reaches the exit only after every level has filled, so the exit is judged
    # against the full position's liquidation; the earlier, smaller positions matter only
    # for being liquidated before the next level fills (`_inside_range`).
    full_position = estimates[-1][1]
    exit_price = _loss_exit(inputs, side)
    found = [
        *_inside_range(side, estimates),
        *_stop(inputs, side, full_position, exit_price),
    ]
    return found or [_ok(inputs, side, full_position, exit_price)]


def _estimate(inputs: PlanRiskInputs, step: LadderStep) -> Decimal | None:
    position = step.position
    return estimated_liquidation_price_in_brackets(
        BracketedPosition(
            position.side,
            position.quantity,
            position.average_entry,
            position.notional / inputs.params.leverage,
        ),
        inputs.brackets,
    ).price


def _loss_exit(inputs: PlanRiskInputs, side: PositionSide) -> Decimal | None:
    params = inputs.params
    return (
        params.stop_loss_price
        if side is PositionSide.LONG
        else params.take_profit_price
    )


def _inside_range(
    side: PositionSide, estimates: list[tuple[LadderStep, Decimal | None]]
) -> list[Verdict]:
    """The first step whose liquidation price is reached before the next level fills."""
    for step, liquidation in estimates:
        if liquidation is None:
            continue
        next_price = step.next_price
        reached = (
            liquidation >= next_price
            if side is PositionSide.LONG
            else liquidation <= next_price
        )
        if reached:
            return [_liquidated_first(side, step, liquidation)]
    return []


def _liquidated_first(
    side: PositionSide, step: LadderStep, liquidation: Decimal
) -> Verdict:
    held = step.position.quantity
    return Verdict(
        _REFUSED,
        "LIQUIDATION_INSIDE_RANGE",
        f"A {side.name.lower()} of {held} (average entry {step.position.average_entry:.2f}) "
        f"would be liquidated near {liquidation:.2f} (an estimate) between this fill and "
        f"the next price the ladder waits at ({step.next_price}), inside the range: the "
        "bot can be liquidated before its ladder is used",
        {
            "liquidation_price": liquidation,
            "next_price": step.next_price,
            "position": held,
        },
    )


def _stop(
    inputs: PlanRiskInputs,
    side: PositionSide,
    liquidation: Decimal | None,
    exit_price: Decimal | None,
) -> list[Verdict]:
    if exit_price is None:
        severity = _REFUSED if inputs.params.leverage > 1 else _WARNING
        return [
            Verdict(
                severity,
                "STOP_LOSS_NEEDED",
                f"A {side.name.lower()} at {inputs.params.leverage}x has no exit on its "
                "losing side; without one it ends in liquidation or at the range's edge",
                {"leverage": Decimal(inputs.params.leverage)},
            )
        ]
    if liquidation is None:
        return []
    gap = _before_liquidation(side, exit_price, liquidation)
    if gap <= 0:
        return [
            Verdict(
                _REFUSED,
                "STOP_LOSS_AFTER_LIQUIDATION",
                f"The exit at {exit_price} is beyond the estimated liquidation price "
                f"{liquidation:.2f}: the position would be liquidated first",
                {"exit_price": exit_price, "liquidation_price": liquidation},
            )
        ]
    atr = inputs.daily_atr
    buffer = inputs.thresholds.min_liq_buffer_atr
    if atr is not None and gap < buffer * atr:
        return [
            Verdict(
                _WARNING,
                "STOP_LOSS_NEAR_LIQUIDATION",
                f"The exit at {exit_price} is {gap:.2f} before the estimated liquidation "
                f"price {liquidation:.2f}, less than {buffer} daily ATR ({atr:.2f})",
                {"gap": gap, "daily_atr": atr, "min_buffer_atr": buffer},
            )
        ]
    return []


def _before_liquidation(
    side: PositionSide, exit_price: Decimal, liquidation: Decimal
) -> Decimal:
    """How far the exit sits on the safe side of the liquidation price (negative: beyond)."""
    return (
        exit_price - liquidation
        if side is PositionSide.LONG
        else liquidation - exit_price
    )


def _ok(
    inputs: PlanRiskInputs,
    side: PositionSide,
    liquidation: Decimal | None,
    exit_price: Decimal | None,
) -> Verdict:
    way = side.name.lower()
    if liquidation is None:
        return Verdict(
            _OK,
            "LIQUIDATION_ESTIMATE",
            f"No price liquidates the {way} at its worst case (an estimate; the "
            "exchange's figure decides)",
        )
    gap = _before_liquidation(side, exit_price, liquidation) if exit_price else None
    where = f", {gap:.2f} before the exit at {exit_price}" if gap is not None else ""
    numbers = {"liquidation_price": liquidation, "mark": inputs.mark}
    return Verdict(
        _OK,
        "LIQUIDATION_ESTIMATE",
        f"Estimated liquidation price of the {way} at its worst case: "
        f"{liquidation:.2f}{where} - an estimate, not a guarantee",
        numbers,
    )
