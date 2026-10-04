"""`EPIC-029C` — one verdict per check on a Grid's parameters (PRO-006 §4.2; ADR D14, D21).

**Four refusals, and no others** — each a certain loss or a certain rejection:

  · `EVERY_CYCLE_LOSES` — even the widest grid's step is at or below
    `2 × maker`, so every completed cycle loses money (both legs rest, so both
    pay the maker fee, ADR D14). When only some grids are that thin it is the
    warning `SOME_GRIDS_LOSE`: the others still earn;
  · `LEVEL_BELOW_MIN_NOTIONAL` — a level's order is worth less than the
    venue's minimum, which the exchange rejects;
  · `LEVEL_ABOVE_MAX_NOTIONAL` — a level's order is worth more than trading's
    per-order cap (ADR D21, O5), which trading rejects. It names the cap and
    the largest capital that would pass;
  · `TOO_MANY_LEVELS` — more orders than the bot may hold open
    (`ExchangeTerms.max_open_orders`: the venue's `MAX_NUM_ORDERS` and
    trading's per-owner cap, ADR O1, whichever is lower), which the exchange
    or trading rejects. Checked before the ladder is built, so a huge
    `grid_count` costs nothing (`grid_evaluation.py`; PR #318 review).

**Warnings** carry the threshold and the measured value. A check that cannot
run (no candles for the ATR) says so as OK, never as a silent pass.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import ROUND_FLOOR, Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    ExchangeTerms,
    MarketView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_derived import (
    GridDerived,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
    GridSpacing,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import GridPlan
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import (
    Verdict,
    VerdictSeverity,
)

_CENT = Decimal("0.01")

OK = VerdictSeverity.OK
WARNING = VerdictSeverity.WARNING
REFUSED = VerdictSeverity.REFUSED


@dataclass(frozen=True, slots=True)
class GridCheckInputs:
    """Everything a check may read, computed once."""

    params: GridParams
    plan: GridPlan
    derived: GridDerived
    terms: ExchangeTerms
    market: MarketView
    thresholds: GridThresholds


def check_break_even(inputs: GridCheckInputs) -> Verdict:
    fees = 2 * inputs.terms.maker_fee
    widest = inputs.derived.largest_step_fraction
    thinnest = inputs.derived.smallest_step_fraction
    numbers = {"widest_step": widest, "thinnest_step": thinnest, "two_maker_fees": fees}
    if widest <= fees:
        return Verdict(
            REFUSED,
            "EVERY_CYCLE_LOSES",
            "Every grid's step is at or below two maker fees, so every cycle loses money",
            numbers,
        )
    if thinnest <= fees:
        losing = sum(1 for grid in inputs.derived.grids if grid.step_fraction <= fees)
        return Verdict(
            WARNING,
            "SOME_GRIDS_LOSE",
            f"{losing} grid(s) have a step at or below two maker fees and lose on each cycle",
            {**numbers, "losing_grids": Decimal(losing)},
        )
    return Verdict(OK, "BREAK_EVEN", "Every grid earns more than its fees", numbers)


def check_min_notional(inputs: GridCheckInputs) -> Verdict:
    """A SELL is sized net of the fee its buy paid in base, so the smallest
    order the bot sends is the smallest level less the taker fee."""
    smallest = min(level.notional for level in inputs.plan.order_levels)
    net = smallest * (1 - inputs.terms.taker_fee)
    minimum = inputs.terms.min_notional
    numbers = {
        "smallest_order": smallest,
        "smallest_after_fee": net,
        "min_notional": minimum,
    }
    if net < minimum:
        return Verdict(
            REFUSED,
            "LEVEL_BELOW_MIN_NOTIONAL",
            f"A level's order is worth {net} after the fee, below the exchange "
            f"minimum of {minimum}",
            numbers,
        )
    return Verdict(
        OK, "MIN_NOTIONAL", "Every order clears the exchange minimum", numbers
    )


def check_max_notional(inputs: GridCheckInputs) -> Verdict:
    largest = max(level.notional for level in inputs.plan.order_levels)
    cap = inputs.terms.max_notional_per_order
    largest_capital = largest_capital_within_cap(inputs.plan, cap)
    numbers = {"largest_order": largest, "cap": cap, "largest_capital": largest_capital}
    if largest > cap:
        return Verdict(
            REFUSED,
            "LEVEL_ABOVE_MAX_NOTIONAL",
            f"A level's order is worth {largest}, above trading's cap of {cap} per order; "
            f"the largest capital that passes is about {largest_capital}",
            numbers,
        )
    return Verdict(OK, "MAX_NOTIONAL", "Every order is within trading's cap", numbers)


def check_open_orders(inputs: GridCheckInputs) -> Verdict:
    """The exact count, after the plan: a price outside the range leaves no
    level EMPTY, so `grid_count + 1` orders (`grid_evaluation.py` has already
    refused anything with more than `max_open_orders` grids)."""
    orders = len(inputs.plan.order_levels)
    allowed = inputs.terms.max_open_orders
    numbers = {"orders": Decimal(orders), "max_open_orders": Decimal(allowed)}
    if orders > allowed:
        return Verdict(
            REFUSED,
            "TOO_MANY_LEVELS",
            f"The plan places {orders} orders; at most {allowed} may be open",
            numbers,
        )
    return Verdict(OK, "OPEN_ORDERS", "The plan fits the open-order limit", numbers)


def largest_capital_within_cap(plan: GridPlan, cap: Decimal) -> Decimal:
    """The largest capital whose every order stays at or under `cap`.

    A BUY level's order is worth at most its capital. A SELL level's base was
    bought at the last price, so it sells for `capital × price / last_price`,
    more than its capital: the highest SELL level is the binding one. Rounding
    quantities down only shrinks an order, so the answer, floored to a cent,
    always passes this check (PR #318 review: `cap × levels` did not).
    """
    markup = max(
        (level.price / plan.last_price for level in plan.sell_levels),
        default=Decimal(1),
    )
    capital = cap * len(plan.order_levels) / max(markup, Decimal(1))
    return capital.quantize(_CENT, rounding=ROUND_FLOOR)


def check_min_step(inputs: GridCheckInputs) -> Verdict:
    thinnest = inputs.derived.smallest_step_fraction
    threshold = inputs.thresholds.min_step_fraction
    numbers = {"thinnest_step": thinnest, "threshold": threshold}
    if thinnest < threshold:
        return Verdict(
            WARNING,
            "STEP_BELOW_MINIMUM",
            f"The thinnest step is {thinnest:.4%}, below {threshold:.2%}; slippage can eat it",
            numbers,
        )
    return Verdict(OK, "STEP_SIZE", "Every step leaves room for slippage", numbers)


def check_range_against_atr(inputs: GridCheckInputs) -> Verdict:
    daily_atr = inputs.market.daily_atr
    if daily_atr is None or daily_atr <= 0:
        return Verdict(
            OK,
            "RANGE_ATR_NOT_CHECKED",
            "No daily candles, so the range was not compared with the ATR",
        )
    params, thresholds = inputs.params, inputs.thresholds
    multiple = (params.upper - params.lower) / daily_atr
    numbers = {
        "range_in_atr": multiple,
        "low": thresholds.range_atr_low,
        "high": thresholds.range_atr_high,
    }
    if not thresholds.range_atr_low <= multiple <= thresholds.range_atr_high:
        return Verdict(
            WARNING,
            "RANGE_OUTSIDE_ATR_BAND",
            f"The range is {multiple:.2f} daily ATRs wide, outside "
            f"{thresholds.range_atr_low}–{thresholds.range_atr_high}",
            numbers,
        )
    return Verdict(OK, "RANGE_ATR", "The range is within the ATR band", numbers)


def check_stop_loss(inputs: GridCheckInputs) -> Verdict:
    stop = inputs.params.stop_loss_price
    lower = inputs.params.lower
    if stop is None:
        return Verdict(OK, "STOP_LOSS_OFF", "No stop loss is set")
    if stop >= lower:
        return Verdict(
            WARNING,
            "STOP_LOSS_INSIDE_RANGE",
            f"The stop loss {stop} is at or above the lower limit {lower}",
            {"stop_loss": stop, "lower": lower},
        )
    return _exit_distance(inputs, "STOP_LOSS", (lower - stop) / lower)


def check_take_profit(inputs: GridCheckInputs) -> Verdict:
    target = inputs.params.take_profit_price
    upper = inputs.params.upper
    if target is None:
        return Verdict(OK, "TAKE_PROFIT_OFF", "No take profit is set")
    if target <= upper:
        return Verdict(
            WARNING,
            "TAKE_PROFIT_INSIDE_RANGE",
            f"The take profit {target} is at or below the upper limit {upper}",
            {"take_profit": target, "upper": upper},
        )
    return _exit_distance(inputs, "TAKE_PROFIT", (target - upper) / upper)


def check_spacing_for_range(inputs: GridCheckInputs) -> Verdict:
    params, limit = inputs.params, inputs.thresholds.arithmetic_max_range_fraction
    width = (params.upper - params.lower) / params.lower
    numbers = {"range_fraction": width, "threshold": limit}
    if params.spacing is GridSpacing.ARITHMETIC and width > limit:
        return Verdict(
            WARNING,
            "ARITHMETIC_ON_WIDE_RANGE",
            f"The range is {width:.1%} wide; arithmetic spacing leaves the upper grids "
            "thin there, and geometric keeps every grid's percentage equal",
            numbers,
        )
    return Verdict(OK, "SPACING", "The spacing suits the range", numbers)


CHECKS: tuple[Callable[[GridCheckInputs], Verdict], ...] = (
    check_break_even,
    check_min_notional,
    check_max_notional,
    check_open_orders,
    check_min_step,
    check_range_against_atr,
    check_stop_loss,
    check_take_profit,
    check_spacing_for_range,
)


def run_checks(inputs: GridCheckInputs) -> tuple[Verdict, ...]:
    return tuple(check(inputs) for check in CHECKS)


def _exit_distance(inputs: GridCheckInputs, name: str, distance: Decimal) -> Verdict:
    low, high = (
        inputs.thresholds.exit_distance_low,
        inputs.thresholds.exit_distance_high,
    )
    numbers = {"distance": distance, "low": low, "high": high}
    if not low <= distance <= high:
        return Verdict(
            WARNING,
            f"{name}_DISTANCE",
            f"The {name.lower().replace('_', ' ')} is {distance:.2%} beyond the range, "
            f"outside {low:.0%}–{high:.0%}",
            numbers,
        )
    return Verdict(
        OK,
        name,
        f"The {name.lower().replace('_', ' ')} distance is within advice",
        numbers,
    )
