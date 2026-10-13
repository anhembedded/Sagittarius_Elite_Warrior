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

@par Direction and sizing (`EPIC-039B`)
The levels are the same for every `TradeDirection`; the direction decides only the opening
trade and which counters only reduce. LONG opens with a market buy of the SELL levels'
quantity (the Spot case above), SHORT with a market sell of the BUY levels' quantity, NEUTRAL
with none; `opening_quantity` is signed (`+` buy, `-` sell). LONG's SELLs and SHORT's BUYs
are `reduce_only`: they can only shrink the position the opening built. The flag means
something on a position venue; the Spot executor never reads it.

`LevelSizing` says how a level's quantity is found. `EQUAL_CAPITAL` is Spot's rule above and
the default. `EQUAL_QUANTITY` gives every order the same base quantity, sized so that every
order filled at once is worth at most the capital times the leverage (decision O2): only then
is the position a function of price (`grid_position_model.py`), which a Futures ladder, its
liquidation estimate and its Neutral mode rely on. Leverage multiplies the capital the
ladder may reach; at 1 it is the capital itself.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.trade_direction import (
    TradeDirection,
)
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


class LevelSizing(str, Enum):
    """How each level's quantity is found (`EPIC-039B`)."""

    #: Capital shared evenly, a BUY buying its share at its own price: a Spot inventory grid.
    EQUAL_CAPITAL = "equal_capital"
    #: The same base quantity at every level: a position grid, where the position is a
    #: function of price.
    EQUAL_QUANTITY = "equal_quantity"


@dataclass(frozen=True, slots=True)
class GridLevel:
    """One rung of the ladder."""

    index: int
    price: Decimal
    side: LevelSide
    quantity: Decimal
    #: The order can only shrink the position (`EPIC-039B`); meaningful on a position venue.
    reduce_only: bool = False

    @property
    def notional(self) -> Decimal:
        return self.price * self.quantity


@dataclass(frozen=True, slots=True)
class GridPlan:
    """The whole ladder, lowest price first, and the trade that opens it."""

    levels: tuple[GridLevel, ...]
    last_price: Decimal
    capital_per_level: Decimal
    #: The opening trade, signed: `+` a market buy, `-` a market sell, `0` none.
    opening_quantity: Decimal
    direction: TradeDirection = TradeDirection.LONG
    #: How the quantities were found; the position model reads only an equal-quantity plan.
    level_sizing: LevelSizing = LevelSizing.EQUAL_CAPITAL

    @property
    def opening_buy_quantity(self) -> Decimal:
        """What the opening market buy buys: the LONG reading of `opening_quantity`."""
        return max(self.opening_quantity, Decimal(0))

    @property
    def uniform_quantity(self) -> Decimal | None:
        """The one base quantity every order of an `EQUAL_QUANTITY` plan has; `None` for an
        equal-capital plan, whose quantities differ by price, or a plan with no order."""
        if self.level_sizing is not LevelSizing.EQUAL_QUANTITY:
            return None
        return next((lv.quantity for lv in self.levels if lv.quantity > 0), None)

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


def plan(
    params: GridParams,
    terms: ExchangeTerms,
    last_price: Decimal,
    level_sizing: LevelSizing = LevelSizing.EQUAL_CAPITAL,
) -> GridPlan:
    """The ladder for `params` when the market is at `last_price`."""
    raw = raw_levels(params.lower, params.upper, params.grid_count, params.spacing)
    empty_index = _empty_index(raw, last_price)
    sides = [
        _side(index, price, last_price, empty_index) for index, price in enumerate(raw)
    ]
    order_count = sum(1 for side in sides if side is not LevelSide.EMPTY)
    sizing = _Sizing(_capital_reached(params) / order_count, terms, last_price)
    quantity_of = _quantity_rule(level_sizing, raw, sizing)
    levels = tuple(
        _level(index, price, side, sizing, quantity_of, params.direction)
        for index, (price, side) in enumerate(zip(raw, sides, strict=True))
    )
    return GridPlan(
        levels,
        last_price,
        sizing.capital_per_level,
        _opening_quantity(params.direction, levels),
        params.direction,
        level_sizing,
    )


def _capital_reached(params: GridParams) -> Decimal:
    """The capital the ladder may reach: the capital itself at leverage 1 (decision O2)."""
    return params.capital_quote * params.leverage


def _opening_quantity(
    direction: TradeDirection, levels: tuple[GridLevel, ...]
) -> Decimal:
    sell = sum((lv.quantity for lv in levels if lv.side is LevelSide.SELL), Decimal(0))
    buy = sum((lv.quantity for lv in levels if lv.side is LevelSide.BUY), Decimal(0))
    return {
        TradeDirection.LONG: sell,
        TradeDirection.SHORT: -buy,
        TradeDirection.NEUTRAL: Decimal(0),
    }[direction]


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


type _QuantityRule = Callable[[LevelSide, Decimal], Decimal]


def _quantity_rule(
    level_sizing: LevelSizing, raw: tuple[Decimal, ...], sizing: _Sizing
) -> _QuantityRule:
    """The quantity of a level of the given side at the given (rounded) price."""
    if level_sizing is LevelSizing.EQUAL_QUANTITY:
        # Sized at the highest level, so every order filled at once is worth at most the
        # capital reached.
        same = _ROUNDING.round_quantity_down(
            sizing.capital_per_level / _highest(raw, sizing), sizing.terms.step_size
        )
        return lambda _side, _price: same

    def equal_capital(side: LevelSide, price: Decimal) -> Decimal:
        bought_at = price if side is LevelSide.BUY else sizing.last_price
        return _ROUNDING.round_quantity_down(
            sizing.capital_per_level / bought_at, sizing.terms.step_size
        )

    return equal_capital


def _highest(raw: tuple[Decimal, ...], sizing: _Sizing) -> Decimal:
    return _ROUNDING.round_price_to_tick(
        max(raw), sizing.terms.tick_size, OrderSide.SELL
    )


def _level(
    index: int,
    raw_price: Decimal,
    side: LevelSide,
    sizing: _Sizing,
    quantity_of: _QuantityRule,
    direction: TradeDirection,
) -> GridLevel:
    order_side = OrderSide.SELL if side is LevelSide.SELL else OrderSide.BUY
    price = _ROUNDING.round_price_to_tick(raw_price, sizing.terms.tick_size, order_side)
    if side is LevelSide.EMPTY:
        return GridLevel(index, price, side, Decimal(0))
    return GridLevel(
        index, price, side, quantity_of(side, price), _only_reduces(direction, side)
    )


def _only_reduces(direction: TradeDirection, side: LevelSide) -> bool:
    """LONG's SELLs shrink a long and SHORT's BUYs shrink a short; NEUTRAL's can open."""
    return (direction is TradeDirection.LONG and side is LevelSide.SELL) or (
        direction is TradeDirection.SHORT and side is LevelSide.BUY
    )
