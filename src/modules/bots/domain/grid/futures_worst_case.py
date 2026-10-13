"""`EPIC-039F` - the largest position a ladder can reach on each side (DESIGN §5.3).

@details A grid's position is a function of price (`grid_position_model.py`). On the way
down every BUY below the price fills, on the way up every SELL above it, so:

  · LONG reaches its extreme at the lowest level: the opening quantity plus every BUY level;
  · SHORT at the highest: the opening quantity (short) plus every SELL level;
  · NEUTRAL has both: all BUY levels long, all SELL levels short, and a plan with two
    extremes has two liquidation estimates.

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
