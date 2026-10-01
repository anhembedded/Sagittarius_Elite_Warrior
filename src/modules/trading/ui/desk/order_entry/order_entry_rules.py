"""`EPIC-028H` — the numbers an order panel shows beside each side's form,
and the reason it refuses to submit, without Qt.

@details One side of the panel (a Spot desk's Buy column, say) is an order
type, a typed price and a typed amount, read against the account and the
symbol's filters (`OrderEntryContext`). `spot_side_figures` answers what that
side shows: what it can spend, the most it can order, the order's total and
fee, and the first thing that stops it, in the order a user fixes them.

The maximum comes from `EPIC-028G`'s estimates, never a formula of its own,
so the panel and the estimates cannot disagree. A Spot market buy is sized at
the last price; the estimate's docstring says what that means when the book
moves.

The Futures side (`EPIC-028I`) is a second function beside this one,
reading the Futures estimates; `DeskProfile` picks which one a desk uses.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_entry_terms import (
    OrderEntryTerms,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_estimates import (
    estimated_fee,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_quantity_rounding_policy import (
    OrderQuantityRoundingPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.spot_order_estimates import (
    SpotOrderTerms,
    spot_max_buy_quantity,
)

_ROUNDING = OrderQuantityRoundingPolicy()
_MAX_PERCENT = 100
_HUNDRED = Decimal(_MAX_PERCENT)


class EntrySide(str, Enum):
    """Which of the panel's sides a form belongs to. A side, not an
    `OrderSide`: on the Futures desk "Sell/Short" may close a long, which
    `manual_order_intent_for()` decides at submit time from the real
    position."""

    BUY = "BUY"
    SELL = "SELL"


@dataclass(frozen=True)
class OrderEntryContext:
    """What the panel read off the exchange for its symbol."""

    symbol: str
    base_asset: str
    quote_asset: str
    terms: OrderEntryTerms
    #: The quote the account can spend; `None` when the account could not be
    #: read, which the panel says rather than showing zero.
    available_quote: Decimal | None
    #: The base asset the account can sell; zero when it holds none.
    free_base: Decimal | None


@dataclass(frozen=True)
class SideInput:
    """What the user typed on one side. `None` is an empty or unreadable
    field."""

    price: Decimal | None = None
    quantity: Decimal | None = None


@dataclass(frozen=True)
class SideFigures:
    """What one side shows, and whether it may submit."""

    #: The price the figures are computed at: the typed limit price, or the
    #: last price for a market order.
    price: Decimal | None
    available: Decimal | None
    available_asset: str
    max_quantity: Decimal | None
    total: Decimal | None
    fee: Decimal | None
    #: Why this side cannot submit; `None` when it can.
    problem: str | None

    @property
    def can_submit(self) -> bool:
        return self.problem is None


def spot_side_figures(
    side: EntrySide,
    order_type: OrderType,
    entry: SideInput,
    context: OrderEntryContext,
    last_price: Decimal | None,
) -> SideFigures:
    """@return One Spot side's figures and the first problem, if any."""
    step = context.terms.rules.step_size_for(order_type)
    fee_rate = context.terms.commission.taker
    price = last_price if order_type is OrderType.MARKET else entry.price
    if side is EntrySide.BUY:
        available, asset = context.available_quote, context.quote_asset
        max_quantity = (
            spot_max_buy_quantity(available, SpotOrderTerms(price, fee_rate), step)
            if available is not None and price is not None and price > 0
            else None
        )
    else:
        available, asset = context.free_base, context.base_asset
        max_quantity = (
            _ROUNDING.round_quantity_down(available, step)
            if available is not None
            else None
        )
    quantity = entry.quantity
    total: Decimal | None = None
    fee: Decimal | None = None
    if quantity is not None and quantity > 0 and price is not None and price > 0:
        total = quantity * price
        fee = estimated_fee(quantity, price, fee_rate)
    return SideFigures(
        price=price,
        available=available,
        available_asset=asset,
        max_quantity=max_quantity,
        total=total,
        fee=fee,
        problem=_first_problem(side, order_type, entry, context, price, max_quantity),
    )


def quantity_at_percent(percent: int, max_quantity: Decimal, step: Decimal) -> Decimal:
    """@return `percent` of `max_quantity`, floored to the lot step, so the
    slider never asks for more than the maximum."""
    if not 0 <= percent <= _MAX_PERCENT:
        raise ValueError(f"percent must be 0..100, got {percent}")
    return _ROUNDING.round_quantity_down(max_quantity * percent / _HUNDRED, step)


def percent_of_max(quantity: Decimal | None, max_quantity: Decimal | None) -> int:
    """@return Where the slider sits for a typed amount, clamped to 0..100."""
    if quantity is None or max_quantity is None or max_quantity <= 0:
        return 0
    return max(0, min(_MAX_PERCENT, int(quantity * _HUNDRED / max_quantity)))


def _first_problem(
    side: EntrySide,
    order_type: OrderType,
    entry: SideInput,
    context: OrderEntryContext,
    price: Decimal | None,
    max_quantity: Decimal | None,
) -> str | None:
    rules = context.terms.rules
    step = rules.step_size_for(order_type)
    if side is EntrySide.SELL and not context.free_base:
        return f"No {context.base_asset} to sell."
    if price is None or price <= 0:
        if order_type is OrderType.MARKET:
            return "No market price yet. Wait for live data."
        return "Enter a price."
    quantity = entry.quantity
    if quantity is None or quantity <= 0:
        return "Enter an amount."
    rounded = _ROUNDING.round_quantity_down(quantity, step)
    if rounded <= 0:
        return f"The amount is below one lot of {step} {context.base_asset}."
    if rounded * price < rules.min_notional:
        return (
            f"The order is worth less than the minimum of "
            f"{rules.min_notional} {context.quote_asset}."
        )
    if max_quantity is None:
        return "The balance could not be read. Check the connection."
    if rounded > max_quantity:
        if side is EntrySide.BUY:
            return (
                f"Not enough {context.quote_asset}: at most {max_quantity} "
                f"{context.base_asset}."
            )
        return f"Not enough {context.base_asset}: at most {max_quantity}."
    return None
