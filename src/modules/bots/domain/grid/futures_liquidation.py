"""`EPIC-039K` — where a Futures replay's position is liquidated, and what that costs.

@details **One formula.** The price comes from `estimated_liquidation_price`
(`trading/contracts/liquidation_estimate.py`, `EPIC-028G`): Binance's one-way formula for one
position, which `EPIC-039F`'s plan guard reads too. This module only decides its inputs, at the
moment asked:

· **the margin** is the position's initial margin, `|quantity| × entry ÷ leverage`, less the
  funding it has paid since it was last flat (funding comes out of the isolated margin).
  `capital_quote` is the margin the user commits (decision O2), and at the ladder's full
  worst-case notional (`capital × leverage`) the initial margin is exactly the capital. Margin
  is not topped up: a realised profit leaves the position and a loss is not replaced;
· **the bracket** is the one the position's notional (`|quantity| × entry`) falls in, whose
  maintenance rate and amount enter the formula.

**Isolated margin only** (decision O5): the other positions of the account do not enter.
Funding that has not yet been charged is not in the margin, so the price is slightly optimistic
between settlements, as `liquidation_estimate.py` says of itself.

**What a liquidation costs.** The position closes at the liquidation price and the isolated
margin is forfeited whole: the loss of the position is its margin, never more (insurance fund)
and never less than what the close already realised (`LiquidationLoss`).

@par Why `backtesting/.../margin_risk_policy.py` keeps its own formula
It prices the paper broker of the *strategy* backtest: `entry × (1 ∓ 1/leverage)`, which is
this formula with a zero maintenance rate and amount (its docstring says so). The two agree
exactly there, and `test_grid_futures_liquidation.py` pins it; they differ by the maintenance
margin otherwise, which the strategy backtest documents as a known limit. Moving that
simulator onto this estimate would change recorded strategy results, which is another task's
decision (`EPIC-037`'s sibling-path rule); nothing here forks the formula.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_brackets import (
    LeverageBrackets,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.liquidation_estimate import (
    LiquidationTerms,
    estimated_liquidation_price,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.position_side import (
    PositionSide,
)

_ZERO = Decimal(0)


@dataclass(frozen=True, slots=True)
class HeldPosition:
    """What is held: a signed quantity at an average entry, and what it has paid in funding."""

    quantity: Decimal
    entry_price: Decimal
    #: Funding paid on it since it was last flat; negative when it has earned.
    funding_paid: Decimal = _ZERO

    @property
    def side(self) -> PositionSide:
        return PositionSide.LONG if self.quantity > 0 else PositionSide.SHORT

    @property
    def notional(self) -> Decimal:
        return abs(self.quantity) * self.entry_price


@dataclass(frozen=True, slots=True)
class Leveraged:
    """A position's leverage and the symbol's brackets: what its liquidation depends on."""

    leverage: int
    brackets: LeverageBrackets


def isolated_margin(position: HeldPosition, leverage: int) -> Decimal:
    """The margin behind `position` right now; never negative."""
    return max(position.notional / leverage - position.funding_paid, _ZERO)


def liquidation_price(position: HeldPosition, terms: Leveraged) -> Decimal | None:
    """The price at which `position` is liquidated, or `None` when no price liquidates it
    (a long at leverage 1) or it is flat."""
    if position.quantity == 0:
        return None
    bracket = terms.brackets.bracket_for(position.notional)
    estimate = estimated_liquidation_price(
        LiquidationTerms(
            side=position.side,
            quantity=abs(position.quantity),
            entry_price=position.entry_price,
            margin=isolated_margin(position, terms.leverage),
            maintenance_margin_rate=bracket.maintenance_margin_rate,
            maintenance_amount=bracket.maintenance_amount,
        )
    )
    return estimate.price


def is_liquidated_at(price: Decimal, position: HeldPosition, limit: Decimal) -> bool:
    """Whether `price` reaches `limit`, the liquidation price of `position`."""
    return price <= limit if position.quantity > 0 else price >= limit


def distance_to_liquidation(
    price: Decimal, position: HeldPosition, limit: Decimal
) -> Decimal:
    """How far `price` stands from `limit`, as a fraction of `price`; zero at or past it."""
    gap = price - limit if position.quantity > 0 else limit - price
    return max(gap, _ZERO) / price


@dataclass(frozen=True, slots=True)
class LiquidationLoss:
    """What closing a liquidated position cost, against what the close already realised."""

    #: The whole margin that stood behind the position: what it loses in total.
    margin_lost: Decimal
    #: Added to the realised profit so the position's total loss is exactly `margin_lost`:
    #: negative when the close realised less than the margin (the maintenance margin the
    #: exchange keeps), positive when the price gapped past it and the insurance fund pays.
    realised_adjustment: Decimal


def loss_of_liquidation(
    margin: Decimal, realised_by_the_close: Decimal
) -> LiquidationLoss:
    """@param realised_by_the_close the profit the close at the liquidation price booked
    (a loss, so negative, for a position that reached it)."""
    return LiquidationLoss(margin, -margin - realised_by_the_close)
