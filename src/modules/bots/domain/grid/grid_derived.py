"""`EPIC-029C` — the numbers a Grid's parameters imply (the report, PRO-006 §1.5).

Shown beside the inputs so the user sees what a choice means before it costs
anything:

  · **per grid** — the step between two neighbouring levels as a percentage of
    the buy, and what is left after both legs pay the maker fee:
    `net = step% − 2 × maker` (ADR D14: both legs of a ladder rest, so both are
    maker fills). The report's bottom and top grids are the first and last;
  · **at the edges** — what the position is worth if the price falls to the
    lower limit (every BUY filled, no SELL), or rises to the upper limit (every
    SELL filled, no BUY), against buy-and-hold of the same capital from the last
    price. These are **before fees**, as in the report: they describe where the
    inventory leaves the user, and the backtest (`EPIC-029D`) is what counts
    fees and slippage;
  · **cycles to recover** — the loss at the lower limit divided by the average
    net profit of one completed cycle. The report's point: a grid below its
    range is not a strategy that cannot lose.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from itertools import pairwise

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    ExchangeTerms,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
    GridSpacing,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import GridPlan
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_spacing import (
    arithmetic_step,
    geometric_ratio,
)


@dataclass(frozen=True, slots=True)
class GridProfit:
    """One grid: the cycle between a buy level and the level above it."""

    buy: Decimal
    sell: Decimal
    step_fraction: Decimal
    net_fraction: Decimal


@dataclass(frozen=True, slots=True)
class EdgeValues:
    """What the capital is worth at one range edge, grid against buy-and-hold."""

    grid: Decimal
    buy_and_hold: Decimal


@dataclass(frozen=True, slots=True)
class GridDerived:
    """Everything the parameters imply, for display and for the checks."""

    #: `(U − L) / N` for arithmetic spacing, `None` for geometric.
    step: Decimal | None
    #: `(U / L) ^ (1 / N)` for geometric spacing, `None` for arithmetic.
    ratio: Decimal | None
    grids: tuple[GridProfit, ...]
    at_lower: EdgeValues
    at_upper: EdgeValues
    cycle_profit_quote: Decimal
    #: `None` when a cycle earns nothing, so the loss is never recovered.
    cycles_to_recover: Decimal | None

    @property
    def bottom(self) -> GridProfit:
        return self.grids[0]

    @property
    def top(self) -> GridProfit:
        return self.grids[-1]

    @property
    def smallest_step_fraction(self) -> Decimal:
        return min(grid.step_fraction for grid in self.grids)

    @property
    def largest_step_fraction(self) -> Decimal:
        return max(grid.step_fraction for grid in self.grids)


def derive(
    params: GridParams, terms: ExchangeTerms, grid_plan: GridPlan
) -> GridDerived:
    grids = _grids(grid_plan.prices, terms.maker_fee)
    cycle_profit = sum(
        (grid_plan.capital_per_level * grid.net_fraction for grid in grids), Decimal(0)
    ) / len(grids)
    at_lower = _at_lower(params, grid_plan)
    return GridDerived(
        step=(
            arithmetic_step(params.lower, params.upper, params.grid_count)
            if params.spacing is GridSpacing.ARITHMETIC
            else None
        ),
        ratio=(
            geometric_ratio(params.lower, params.upper, params.grid_count)
            if params.spacing is GridSpacing.GEOMETRIC
            else None
        ),
        grids=grids,
        at_lower=at_lower,
        at_upper=_at_upper(params, grid_plan),
        cycle_profit_quote=cycle_profit,
        cycles_to_recover=_cycles_to_recover(
            params.capital_quote - at_lower.grid, cycle_profit
        ),
    )


def _grids(prices: tuple[Decimal, ...], maker_fee: Decimal) -> tuple[GridProfit, ...]:
    grids: list[GridProfit] = []
    for buy, sell in pairwise(prices):
        step_fraction = (sell - buy) / buy
        grids.append(
            GridProfit(buy, sell, step_fraction, step_fraction - 2 * maker_fee)
        )
    return tuple(grids)


def _cash_after_opening(params: GridParams, grid_plan: GridPlan) -> Decimal:
    return params.capital_quote - grid_plan.opening_buy_quantity * grid_plan.last_price


def _at_lower(params: GridParams, grid_plan: GridPlan) -> EdgeValues:
    buys = grid_plan.buy_levels
    base = grid_plan.opening_buy_quantity + sum((b.quantity for b in buys), Decimal(0))
    spent = sum((b.notional for b in buys), Decimal(0))
    cash = _cash_after_opening(params, grid_plan) - spent
    return EdgeValues(
        grid=base * params.lower + cash,
        buy_and_hold=params.capital_quote * params.lower / grid_plan.last_price,
    )


def _at_upper(params: GridParams, grid_plan: GridPlan) -> EdgeValues:
    proceeds = sum((s.notional for s in grid_plan.sell_levels), Decimal(0))
    return EdgeValues(
        grid=_cash_after_opening(params, grid_plan) + proceeds,
        buy_and_hold=params.capital_quote * params.upper / grid_plan.last_price,
    )


def _cycles_to_recover(loss: Decimal, cycle_profit: Decimal) -> Decimal | None:
    if loss <= 0:
        return Decimal(0)
    if cycle_profit <= 0:
        return None
    return loss / cycle_profit
