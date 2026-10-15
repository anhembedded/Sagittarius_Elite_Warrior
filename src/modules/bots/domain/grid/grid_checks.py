"""`EPIC-029C` — one verdict per check on a Grid's parameters (PRO-006 §4.2; ADR D14, D21).

**Refusals** — each a certain loss or a certain rejection, the rules of the
exchange and of money (`EPIC-034`'s D7; `grid_constraints.py` is the table that
says which codes block and which advise, and a test holds every check to it):

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
    (`ExchangeTerms.max_open_orders`: trading's per-owner cap, ADR O1, which
    stays below Binance Spot's `MAX_NUM_ORDERS` of 200; that filter itself is
    not read), which trading rejects. Checked before the ladder is built, so a huge
    `grid_count` costs nothing (`grid_evaluation.py`; PR #318 review);
  · `LEVEL_OUTSIDE_PRICE_BAND` — a level's price is outside the band the venue
    accepts for its side (`ExchangeTerms.price_band`, Binance Spot's
    `PERCENT_PRICE_BY_SIDE`), which the exchange rejects (`BUG-147`). The band
    follows the market, so it is judged at the current price;
  · `STOP_LOSS_INSIDE_RANGE` / `TAKE_PROFIT_INSIDE_RANGE` — an exit on the
    wrong side of the range: a stop at or above the lower limit would fire
    inside the grid, a take profit at or below the upper limit would close it
    while it still earns (`EPIC-034F`; they advised only before D7).

The account's constraints (the balance, the key) are `grid_account_checks.py`.

**Warnings** carry the threshold and the measured value. A check that cannot
run (no candles for the ATR) says so as OK, never as a silent pass.
"""

from __future__ import annotations

from decimal import ROUND_FLOOR, Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_advice_texts import (
    STOP_LOSS_SIDE,
    TAKE_PROFIT_SIDE,
    ExitSide,
    arithmetic_spacing_advice,
    exit_distance_advice,
    foreign_orders_advice,
    losing_grids_advice,
    range_atr_advice,
    suggested_atr_range,
    thin_step_advice,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_check_inputs import (
    GridCheckInputs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_order_sizing import (
    find_breach,
    smallest_order,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridSpacing,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import GridPlan
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import (
    Verdict,
    VerdictSeverity,
)

_CENT = Decimal("0.01")

OK = VerdictSeverity.OK
WARNING = VerdictSeverity.WARNING
REFUSED = VerdictSeverity.REFUSED


def check_break_even(inputs: GridCheckInputs) -> Verdict:
    fees = 2 * inputs.terms.maker_fee
    widest = inputs.derived.largest_step_fraction
    thinnest = inputs.derived.smallest_step_fraction
    numbers = {"widest_step": widest, "thinnest_step": thinnest, "two_maker_fees": fees}
    if widest <= fees:
        return Verdict(
            REFUSED,
            "EVERY_CYCLE_LOSES",
            f"Every grid's step ({widest:.3%} at most) is at or below two maker "
            f"fees ({fees:.3%}), so every cycle loses money; widen the range or "
            "use fewer grids",
            numbers,
        )
    if thinnest <= fees:
        losing = sum(1 for grid in inputs.derived.grids if grid.step_fraction <= fees)
        advice, grids = losing_grids_advice(inputs, fees)
        return Verdict(
            WARNING,
            "SOME_GRIDS_LOSE",
            advice.text,
            {
                **numbers,
                "losing_grids": Decimal(losing),
                "suggested_grids": Decimal(grids),
            },
        )
    return Verdict(OK, "BREAK_EVEN", "Every grid earns more than its fees", numbers)


def check_min_notional(inputs: GridCheckInputs) -> Verdict:
    """Every order the executor sends is worth the exchange's minimum (`BUG-212`).

    The orders are sized by `grid_order_sizing`, the same function the executor lays its
    ladder from: SELLs net of the opening's fee and floored to the step, and the counter
    orders of each pair of levels."""
    smallest = smallest_order(inputs.plan, inputs.terms)
    minimum = inputs.terms.min_notional
    numbers = {"min_notional": minimum}
    if smallest is not None:
        numbers["smallest_order"] = smallest.notional
    breach = find_breach(inputs.params, inputs.plan, inputs.terms)
    if breach is None:
        return Verdict(
            OK, "MIN_NOTIONAL", "Every order clears the exchange minimum", numbers
        )
    if breach.minimum_capital is not None:
        numbers["minimum_capital"] = breach.minimum_capital
    return Verdict(
        REFUSED,
        "LEVEL_BELOW_MIN_NOTIONAL",
        breach.text(inputs.market.base_asset, inputs.market.quote_asset),
        numbers,
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


def check_foreign_orders(inputs: GridCheckInputs) -> Verdict:
    """Orders already open on the symbol share the exchange's open-order limit
    with the plan's, and the bot neither placed nor will manage them
    (`EPIC-035V`, L7). Advice: the exchange, not this check, is the limit."""
    foreign = inputs.market.foreign_open_orders
    if foreign is None:
        return Verdict(
            OK,
            "FOREIGN_ORDERS_NOT_READ",
            "The orders already open on the symbol were not read, so they were "
            "not counted against the open-order limit",
        )
    orders = len(inputs.plan.order_levels)
    allowed = inputs.terms.max_open_orders
    numbers = {
        "orders": Decimal(orders),
        "foreign": Decimal(foreign),
        "total": Decimal(orders + foreign),
        "max_open_orders": Decimal(allowed),
    }
    if foreign > 0:
        advice, fitting = foreign_orders_advice(foreign, orders, allowed)
        return Verdict(
            WARNING,
            "FOREIGN_OPEN_ORDERS",
            advice.text,
            {**numbers, "suggested_grids": Decimal(fitting)},
        )
    return Verdict(
        OK, "NO_FOREIGN_ORDERS", "No other order is open on the symbol", numbers
    )


def check_price_band(inputs: GridCheckInputs) -> Verdict:
    band = inputs.terms.price_band
    if band is None:
        return Verdict(
            OK,
            "PRICE_BAND_NOT_PUBLISHED",
            "The venue publishes no price band, so the levels were not compared with one",
        )
    last = inputs.plan.last_price
    lowest_buy, highest_buy = last * band.buy_down, last * band.buy_up
    lowest_sell, highest_sell = last * band.sell_down, last * band.sell_up
    numbers = {
        "last_price": last,
        "lowest_buy_allowed": lowest_buy,
        "highest_sell_allowed": highest_sell,
    }
    for level in inputs.plan.buy_levels:
        if not lowest_buy <= level.price <= highest_buy:
            return _outside_band(level.price, "BUY", (lowest_buy, highest_buy), numbers)
    for level in inputs.plan.sell_levels:
        if not lowest_sell <= level.price <= highest_sell:
            return _outside_band(
                level.price, "SELL", (lowest_sell, highest_sell), numbers
            )
    return Verdict(
        OK, "PRICE_BAND", "Every level is inside the venue's price band", numbers
    )


def _outside_band(
    price: Decimal,
    side: str,
    allowed: tuple[Decimal, Decimal],
    numbers: dict[str, Decimal],
) -> Verdict:
    low, high = allowed
    return Verdict(
        REFUSED,
        "LEVEL_OUTSIDE_PRICE_BAND",
        f"A {side} level at {price} is outside the {low:f}–{high:f} the exchange "
        f"accepts for a {side} at the current price {numbers['last_price']}; "
        "narrow the range",
        {**numbers, "level_price": price},
    )


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
        advice, grids = thin_step_advice(inputs)
        return Verdict(
            WARNING,
            "STEP_BELOW_MINIMUM",
            advice.text,
            {**numbers, "suggested_grids": Decimal(grids)},
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
        lower, upper = suggested_atr_range(inputs, daily_atr)
        return Verdict(
            WARNING,
            "RANGE_OUTSIDE_ATR_BAND",
            range_atr_advice(inputs, daily_atr, multiple).text,
            {
                **numbers,
                "daily_atr": daily_atr,
                "range_width": params.upper - params.lower,
                "suggested_lower": lower,
                "suggested_upper": upper,
            },
        )
    return Verdict(OK, "RANGE_ATR", "The range is within the ATR band", numbers)


def check_stop_loss(inputs: GridCheckInputs) -> Verdict:
    stop = inputs.params.stop_loss_price
    lower = inputs.params.lower
    if stop is None:
        return Verdict(OK, "STOP_LOSS_OFF", "No stop loss is set")
    if stop >= lower:
        return Verdict(
            REFUSED,
            "STOP_LOSS_INSIDE_RANGE",
            f"The stop loss {stop} is at or above the lower limit {lower}; put it "
            "below the range",
            {"stop_loss": stop, "lower": lower},
        )
    return _exit_distance(inputs, STOP_LOSS_SIDE, stop, (lower - stop) / lower)


def check_take_profit(inputs: GridCheckInputs) -> Verdict:
    target = inputs.params.take_profit_price
    upper = inputs.params.upper
    if target is None:
        return Verdict(OK, "TAKE_PROFIT_OFF", "No take profit is set")
    if target <= upper:
        return Verdict(
            REFUSED,
            "TAKE_PROFIT_INSIDE_RANGE",
            f"The take profit {target} is at or below the upper limit {upper}; put "
            "it above the range",
            {"take_profit": target, "upper": upper},
        )
    return _exit_distance(inputs, TAKE_PROFIT_SIDE, target, (target - upper) / upper)


def check_spacing_for_range(inputs: GridCheckInputs) -> Verdict:
    params, limit = inputs.params, inputs.thresholds.arithmetic_max_range_fraction
    width = (params.upper - params.lower) / params.lower
    numbers = {"range_fraction": width, "threshold": limit}
    if params.spacing is GridSpacing.ARITHMETIC and width > limit:
        return Verdict(
            WARNING,
            "ARITHMETIC_ON_WIDE_RANGE",
            arithmetic_spacing_advice(inputs, limit).text,
            numbers,
        )
    return Verdict(OK, "SPACING", "The spacing suits the range", numbers)


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
