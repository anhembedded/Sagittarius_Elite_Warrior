"""`BUG-210` — the words of each Grid advice, built from the numbers a check measured.

`grid_checks.py` decides (a threshold crossed or not); this module only writes what the
decision means, through `Advice`, so every sentence carries the contract of
`grid_advice.py`: the real figure with its unit, the recommended value in quote terms, the
consequence and the action. No threshold or comparison lives here, and a recommendation is
the value the threshold itself asks for, so following it clears the advice.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_advice import (
    Advice,
    Figures,
    plain,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_check_inputs import (
    GridCheckInputs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_derived import (
    GridProfit,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
    GridSpacing,
)

_TWO = Decimal(2)


def figures_of(inputs: GridCheckInputs) -> Figures:
    return Figures.of(inputs.terms, inputs.market)


# --- the range against the daily ATR -------------------------------------------


def suggested_atr_range(
    inputs: GridCheckInputs, daily_atr: Decimal
) -> tuple[Decimal, Decimal]:
    """The range with the user's own middle and a width in the middle of the advised ATR
    band: following it passes `check_range_against_atr`."""
    thresholds, params = inputs.thresholds, inputs.params
    half_width = (thresholds.range_atr_low + thresholds.range_atr_high) / 4 * daily_atr
    middle = (params.lower + params.upper) / 2
    figures = figures_of(inputs)
    return figures.snap(middle - half_width), figures.snap(middle + half_width)


def range_atr_advice(
    inputs: GridCheckInputs, daily_atr: Decimal, multiple: Decimal
) -> Advice:
    figures, thresholds = figures_of(inputs), inputs.thresholds
    low, high = thresholds.range_atr_low, thresholds.range_atr_high
    width = inputs.params.upper - inputs.params.lower
    wide = multiple > high
    suggested = suggested_atr_range(inputs, daily_atr)
    finding = (
        f"{'Wide' if wide else 'Narrow'} range: {figures.money(width)} "
        f"({multiple:.2f} daily ATRs). {figures.base} usually moves about "
        f"{figures.money(daily_atr)} a day (the daily ATR, the average true range of "
        f"one day's price movement), so {plain(low)}–{plain(high)} days of movement is "
        f"{figures.span(low * daily_atr, high * daily_atr)}."
    )
    consequence = (
        "A wider range fills less often and earns more slowly, but price leaves it "
        "less often."
        if wide
        else "A narrower range fills more often, but price leaves it sooner, and the "
        "bot then waits idle until price returns."
    )
    action = f"Try {figures.span(*suggested)}, or use Suggest from ATR."
    return Advice(finding, consequence, action)


# --- the step ------------------------------------------------------------------


def grids_with_step_at_least(
    params: GridParams, fraction: Decimal, *, strictly_above: bool
) -> int:
    """The most grids this range can hold while its thinnest step stays at (or strictly
    above) `fraction` of the price it is bought at; `0` when not even one grid does.

    Arithmetic: the thinnest step is the top one, `s / (U − s)` with `s = (U − L) / N`.
    Geometric: every step is `(U / L)^(1/N) − 1`.
    """
    lower, upper = params.lower, params.upper
    if params.spacing is GridSpacing.ARITHMETIC:
        bound = (upper - lower) * (1 + fraction) / (fraction * upper)
    else:
        bound = (upper / lower).ln() / (1 + fraction).ln()
    if strictly_above:
        return max(int(bound.to_integral_value(rounding=ROUND_CEILING)) - 1, 0)
    return int(bound.to_integral_value(rounding=ROUND_FLOOR))


def _thinnest(inputs: GridCheckInputs) -> GridProfit:
    return min(inputs.derived.grids, key=lambda grid: grid.step_fraction)


def _grids_to_use(grids: int) -> str:
    if grids < 1:
        return "Widen the range"
    return f"Use {grids} grids or fewer, or widen the range"


def thin_step_advice(inputs: GridCheckInputs) -> tuple[Advice, int]:
    """The advice and the grid count that clears it."""
    figures, threshold = figures_of(inputs), inputs.thresholds.min_step_fraction
    thinnest = _thinnest(inputs)
    grids = grids_with_step_at_least(inputs.params, threshold, strictly_above=False)
    finding = (
        f"The thinnest grid step is {thinnest.step_fraction:.3%} "
        f"({figures.money(thinnest.sell - thinnest.buy)}, from {figures.price(thinnest.buy)} "
        f"to {figures.price(thinnest.sell)}). At least {threshold:.2%} is advised, which "
        f"is {figures.money(threshold * thinnest.buy)} at that price."
    )
    consequence = (
        "Slippage (the gap between the price you expect and the price you get) can eat "
        "a step this thin, so a cycle there earns little or loses."
    )
    return Advice(finding, consequence, f"{_grids_to_use(grids)}."), grids


def losing_grids_advice(inputs: GridCheckInputs, fees: Decimal) -> tuple[Advice, int]:
    figures, derived = figures_of(inputs), inputs.derived
    losing = sum(1 for grid in derived.grids if grid.step_fraction <= fees)
    thinnest = _thinnest(inputs)
    grids = grids_with_step_at_least(inputs.params, fees, strictly_above=True)
    finding = (
        f"{losing} of {len(derived.grids)} grids have a step of {fees:.2%} or less, "
        f"which is two maker fees ({figures.money(fees * thinnest.buy)} at the thinnest "
        f"grid's price {figures.price(thinnest.buy)}); the thinnest step is "
        f"{thinnest.step_fraction:.3%} ({figures.money(thinnest.sell - thinnest.buy)})."
    )
    consequence = (
        "Each completed cycle on those grids loses money; the others still earn."
    )
    return Advice(finding, consequence, f"{_grids_to_use(grids)}."), grids


# --- the orders already open -----------------------------------------------------


def foreign_orders_advice(
    foreign: int, orders: int, allowed: int
) -> tuple[Advice, int]:
    """The advice and the grids that still fit beside the other orders (a plan of `N` grids
    places `N + 1` orders); `0` when none do."""
    total = orders + foreign
    fitting = max(allowed - foreign - 1, 0)
    plural = "orders are" if foreign != 1 else "order is"
    finding = (
        f"{foreign} other {plural} already open on this symbol, and this plan places "
        f"{orders} more: {total} open orders against a limit of {allowed}."
    )
    consequence = (
        "This bot will not manage the others, and the exchange counts them against "
        "the same limit."
    )
    if total > allowed:
        action = (
            f"Cancel the other orders on the exchange, or use {fitting} grids or fewer."
            if fitting
            else "Cancel the other orders on the exchange first."
        )
    else:
        action = (
            f"They leave room for {allowed - total} more; cancel them on the exchange "
            "if you did not mean to keep them."
        )
    return Advice(finding, consequence, action), fitting


# --- the spacing -----------------------------------------------------------------


def arithmetic_spacing_advice(inputs: GridCheckInputs, limit: Decimal) -> Advice:
    figures, params, derived = figures_of(inputs), inputs.params, inputs.derived
    width = (params.upper - params.lower) / params.lower
    step = derived.step or Decimal(0)
    finding = (
        f"The range is {width:.1%} wide ({figures.money(params.upper - params.lower)}, "
        f"{figures.span(params.lower, params.upper)}), above the {limit:.0%} that "
        f"arithmetic spacing suits. Every grid is {figures.money(step)}, which is "
        f"{derived.bottom.step_fraction:.2%} of the price at the bottom but only "
        f"{derived.top.step_fraction:.2%} at the top."
    )
    consequence = "The upper grids earn less per cycle against the same fees."
    action = (
        "Set Spacing to Geometric (every grid the same percentage), or narrow the "
        f"range to {figures.span(params.lower, params.lower * (1 + limit))}."
    )
    return Advice(finding, consequence, action)


# --- the exits -------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ExitSide:
    """Which exit and which edge of the range it is measured from."""

    name: str
    edge_name: str
    below: bool
    #: Whether it is the exit that limits a loss; the advice is about the loss or the gain
    #: whichever side of the range it sits on (`EPIC-039I`: a SHORT stop loss sits above).
    is_stop_loss: bool


STOP_LOSS_SIDE = ExitSide("stop loss", "lower", below=True, is_stop_loss=True)
TAKE_PROFIT_SIDE = ExitSide("take profit", "upper", below=False, is_stop_loss=False)
SHORT_STOP_LOSS_SIDE = ExitSide("stop loss", "upper", below=False, is_stop_loss=True)
SHORT_TAKE_PROFIT_SIDE = ExitSide(
    "take profit", "lower", below=True, is_stop_loss=False
)


def exit_distance_advice(
    inputs: GridCheckInputs, side: ExitSide, price: Decimal, distance: Decimal
) -> Advice:
    figures, thresholds = figures_of(inputs), inputs.thresholds
    low, high = thresholds.exit_distance_low, thresholds.exit_distance_high
    edge = inputs.params.lower if side.edge_name == "lower" else inputs.params.upper
    direction = -1 if side.below else 1
    nearest, farthest = (edge * (1 + direction * share) for share in (low, high))
    advised = figures.span(min(nearest, farthest), max(nearest, farthest))
    place = "below" if side.below else "above"
    finding = (
        f"The {side.name} at {figures.money(price)} is {distance:.2%} "
        f"({figures.money(abs(price - edge))}) {place} the {side.edge_name} limit "
        f"{figures.price(edge)}, outside the advised {low:.0%}–{high:.0%} ({advised})."
    )
    return Advice(
        finding,
        _exit_consequence(side, too_close=distance < low),
        f"Try a {side.name} between {advised}.",
    )


def _exit_consequence(side: ExitSide, *, too_close: bool) -> str:
    if side.is_stop_loss:
        return (
            "Ordinary price movement can reach it and close the bot early."
            if too_close
            else "Price can fall a long way, and the bot can lose much more, before it acts."
        )
    return (
        "It closes the bot soon after price leaves the range, before the move has paid."
        if too_close
        else "Price may rarely get that far, so the bot may wait out of the range."
    )
