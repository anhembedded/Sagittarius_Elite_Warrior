"""`EPIC-039F` - the positions a ladder passes through, and the largest on each side (DESIGN §5.3).

@details A grid's position is a function of price (`grid_position_model.py`). On the way
down every BUY below the price fills, on the way up every SELL above it, so:

  · LONG reaches its extreme at the lowest level: the opening quantity plus every BUY level;
  · SHORT at the highest: the opening quantity (short) plus every SELL level;
  · NEUTRAL has both: all BUY levels long, all SELL levels short, and a plan with two
    extremes has two liquidation estimates.

`ladder_steps` lists every position on the way, in the order the fills reach it, each with the
price of the level that would fill next (or the range's edge after the last). A grid can be
liquidated *between* two levels: at higher leverage the position held after the 61,000 BUY may
liquidate above the 60,000 level (review of PR #486), so the guard estimates every step, not
only the far edge.

Each extreme carries the **average entry** of what it holds (the opening trade at the plan's
last price, each level at its own price), because the liquidation formula reads the entry.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.trade_direction import (
    TradeDirection,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import (
    GridPlan,
    LevelSide,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.position_side import (
    PositionSide,
)

_ZERO = Decimal(0)


@dataclass(frozen=True, slots=True)
class WorstCasePosition:
    side: PositionSide
    quantity: Decimal
    average_entry: Decimal

    @property
    def notional(self) -> Decimal:
        return self.quantity * self.average_entry


def worst_case_positions(plan: GridPlan) -> tuple[WorstCasePosition, ...]:
    """The extreme position of each side the plan can be exposed on; empty when none."""
    fills = _fills(plan)
    opening = plan.opening_quantity
    long_fills = fills[LevelSide.BUY]
    short_fills = fills[LevelSide.SELL]
    if plan.direction is TradeDirection.LONG:
        return _extreme(PositionSide.LONG, opening, plan.last_price, long_fills)
    if plan.direction is TradeDirection.SHORT:
        return _extreme(PositionSide.SHORT, -opening, plan.last_price, short_fills)
    return _extreme(PositionSide.LONG, _ZERO, plan.last_price, long_fills) + _extreme(
        PositionSide.SHORT, _ZERO, plan.last_price, short_fills
    )


def _fills(plan: GridPlan) -> dict[LevelSide, list[tuple[Decimal, Decimal]]]:
    by_side: dict[LevelSide, list[tuple[Decimal, Decimal]]] = {
        LevelSide.BUY: [],
        LevelSide.SELL: [],
    }
    for level in plan.order_levels:
        by_side[level.side].append((level.quantity, level.price))
    return by_side


def _extreme(
    side: PositionSide,
    opening: Decimal,
    opening_price: Decimal,
    levels: list[tuple[Decimal, Decimal]],
) -> tuple[WorstCasePosition, ...]:
    held = [(opening, opening_price), *levels]
    quantity = sum((q for q, _ in held), _ZERO)
    if quantity <= 0:
        return ()
    entry = sum((q * price for q, price in held), _ZERO) / quantity
    return (WorstCasePosition(side, quantity, entry),)


@dataclass(frozen=True, slots=True)
class LadderStep:
    """A position the ladder holds after a fill, and where the next fill waits."""

    position: WorstCasePosition
    #: The price of the level that fills next, or the range's edge once none is left.
    next_price: Decimal


def ladder_steps(
    plan: GridPlan, lower: Decimal, upper: Decimal
) -> tuple[LadderStep, ...]:
    """Every position of each exposed side, in fill order (LONG's side first), each judged
    against the next price the ladder reaches; `lower` and `upper` are the range's edges."""
    fills = _fills(plan)
    buys = sorted(fills[LevelSide.BUY], key=lambda fill: -fill[1])
    sells = sorted(fills[LevelSide.SELL], key=lambda fill: fill[1])
    opening = plan.opening_quantity
    long_open = opening if plan.direction is TradeDirection.LONG else _ZERO
    short_open = -opening if plan.direction is TradeDirection.SHORT else _ZERO
    steps: list[LadderStep] = []
    if plan.direction is not TradeDirection.SHORT:
        steps += _steps(PositionSide.LONG, long_open, plan.last_price, buys, lower)
    if plan.direction is not TradeDirection.LONG:
        steps += _steps(PositionSide.SHORT, short_open, plan.last_price, sells, upper)
    return tuple(steps)


def _steps(
    side: PositionSide,
    opening: Decimal,
    opening_price: Decimal,
    levels: list[tuple[Decimal, Decimal]],
    edge: Decimal,
) -> list[LadderStep]:
    steps: list[LadderStep] = []
    held = [(opening, opening_price)] if opening > 0 else []
    prices_after = [price for _, price in levels] + [edge]
    if held:
        steps.extend(_step(side, held, prices_after[0]))
    for index, level in enumerate(levels):
        held = [*held, level]
        steps.extend(_step(side, held, prices_after[index + 1]))
    return steps


def _step(
    side: PositionSide, held: list[tuple[Decimal, Decimal]], next_price: Decimal
) -> list[LadderStep]:
    quantity = sum((q for q, _ in held), _ZERO)
    if quantity <= 0:
        return []
    entry = sum((q * price for q, price in held), _ZERO) / quantity
    return [LadderStep(WorstCasePosition(side, quantity, entry), next_price)]
