"""`EPIC-029C` — the ladder a Grid would place: prices, sides and quantities (ADR §3.2).

· **Prices** are rounded to `tick_size` by side, the same rule as trading's
  `OrderQuantityRoundingPolicy.round_price_to_tick`: a BUY rounds down, a
  SELL up, so neither pays worse than the user's level. An EMPTY level rounds
  down, like a BUY.
· **Sides.** Levels strictly below the last price are BUY, strictly above are
  SELL. The level nearest the price stays EMPTY when it is within half a
  step of it (ties go to the lower level), so no order is marketable at the
  taker fee. With the price outside the range, no level is that close and
  every level holds an order.
· **Capital** is split evenly across the levels that hold an order (the
  report: 10,000 USDT over 10 orders is 1,000 per level).
· **Quantities** are rounded down to `step_size` (never more than the level's
  capital). A BUY level buys its capital's worth at its own price. A SELL
  level sells base bought by the opening purchase at the last price, so its
  quantity is its capital's worth at the last price — the report's start-up,
  where half the capital buys the base for the levels above.
· **The opening purchase** is the total quantity of the SELL levels.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    ExchangeTerms,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_spacing import (
    raw_levels,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_quantity_rounding_policy import (
    OrderQuantityRoundingPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide

_ROUNDING = OrderQuantityRoundingPolicy()
_HALF = Decimal("0.5")


class LevelSide(str, Enum):
    """What a level holds at start."""

    BUY = "BUY"
    SELL = "SELL"
    EMPTY = "EMPTY"


@dataclass(frozen=True, slots=True)
class GridLevel:
    """One rung of the ladder."""

    index: int
    price: Decimal
    side: LevelSide
    quantity: Decimal

    @property
    def notional(self) -> Decimal:
        return self.price * self.quantity


@dataclass(frozen=True, slots=True)
class GridPlan:
    """The whole ladder, lowest price first, and the purchase that opens it."""

    levels: tuple[GridLevel, ...]
    last_price: Decimal
    capital_per_level: Decimal
    opening_buy_quantity: Decimal

    @property
    def order_levels(self) -> tuple[GridLevel, ...]:
        return tuple(
            level for level in self.levels if level.side is not LevelSide.EMPTY
        )

    @property
    def buy_levels(self) -> tuple[GridLevel, ...]:
        return tuple(level for level in self.levels if level.side is LevelSide.BUY)

    @property
    def sell_levels(self) -> tuple[GridLevel, ...]:
        return tuple(level for level in self.levels if level.side is LevelSide.SELL)

    @property
    def prices(self) -> tuple[Decimal, ...]:
        return tuple(level.price for level in self.levels)


def plan(params: GridParams, terms: ExchangeTerms, last_price: Decimal) -> GridPlan:
    """The ladder for `params` when the market is at `last_price`."""
    raw = raw_levels(params.lower, params.upper, params.grid_count, params.spacing)
    empty_index = _empty_index(raw, last_price)
    sides = [
        _side(index, price, last_price, empty_index) for index, price in enumerate(raw)
    ]
    order_count = sum(1 for side in sides if side is not LevelSide.EMPTY)
    sizing = _Sizing(params.capital_quote / order_count, terms, last_price)
    levels = tuple(
        _level(index, price, side, sizing)
        for index, (price, side) in enumerate(zip(raw, sides, strict=True))
    )
    opening = sum(
        (level.quantity for level in levels if level.side is LevelSide.SELL), Decimal(0)
    )
    return GridPlan(levels, last_price, sizing.capital_per_level, opening)


def _empty_index(raw: tuple[Decimal, ...], last_price: Decimal) -> int | None:
    """The level nearest `last_price` if it is within half a step of it, else `None`.

    The step is the grid the price sits in, or, beyond an edge, the edge grid.
    Inside the range the nearest level always qualifies (it is the nearer end of
    the price's own grid); beyond an edge it qualifies only within half the
    edge grid, so a price far outside the range leaves every level an order.
    """
    nearest = min(
        range(len(raw)), key=lambda index: (abs(raw[index] - last_price), index)
    )
    toward_price = nearest - 1 if last_price < raw[nearest] else nearest + 1
    neighbour = (
        toward_price if 0 <= toward_price < len(raw) else 2 * nearest - toward_price
    )
    half_step = abs(raw[neighbour] - raw[nearest]) * _HALF
    return nearest if abs(raw[nearest] - last_price) <= half_step else None


def _side(
    index: int, price: Decimal, last_price: Decimal, empty_index: int | None
) -> LevelSide:
    if index == empty_index:
        return LevelSide.EMPTY
    return LevelSide.BUY if price < last_price else LevelSide.SELL


@dataclass(frozen=True, slots=True)
class _Sizing:
    """What every level's quantity is computed from."""

    capital_per_level: Decimal
    terms: ExchangeTerms
    last_price: Decimal


def _level(
    index: int, raw_price: Decimal, side: LevelSide, sizing: _Sizing
) -> GridLevel:
    order_side = OrderSide.SELL if side is LevelSide.SELL else OrderSide.BUY
    price = _ROUNDING.round_price_to_tick(raw_price, sizing.terms.tick_size, order_side)
    if side is LevelSide.EMPTY:
        return GridLevel(index, price, side, Decimal(0))
    bought_at = price if side is LevelSide.BUY else sizing.last_price
    quantity = _ROUNDING.round_quantity_down(
        sizing.capital_per_level / bought_at, sizing.terms.step_size
    )
    return GridLevel(index, price, side, quantity)
