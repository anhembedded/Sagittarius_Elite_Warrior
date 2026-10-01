"""`EPIC-028H` — the numbers an order panel shows beside each side's form,
and the reason it refuses to submit, without Qt.

@details One side of the panel (a Spot desk's Buy column, say) is an order
type, a typed price and a typed amount, read against the account and the
symbol's filters (`OrderEntryContext`). `spot_side_figures` answers what that
side shows: what it can spend, the most it can order, the order's total and
fee, and the first thing that stops it, in the order a user fixes them.

The maximum comes from `EPIC-028G`'s estimates, never a formula of its own,
so the panel and the estimates cannot disagree.

`EPIC-028O` adds three things:
- **every maximum also respects the app's per-order notional limit**
  (`OrderEntryContext.notional_limit`, the figure `ExecuteOrderCommandHandler`
  refuses an order over), so a 100 % slider never asks for an order the app's
  own gate would refuse;
- **a Spot market buy is sized by the quote it spends** (`quoteOrderQty`):
  the user types a total, and the base quantity is the exchange's to decide.
  Its maximum is the available quote, capped by the limit;
- **a stop-limit** needs a stop price on the waiting side of the last price
  (`check_stop_trigger_side`, the rule the execute gate applies), and is
  otherwise a limit order at its limit price.

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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.spot_order_estimates import (
    SpotOrderTerms,
    spot_max_buy_quantity,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.stop_price_check import (
    StopPriceCheck,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.stop_trigger_side import (
    check_stop_trigger_side,
)

_ROUNDING = OrderQuantityRoundingPolicy()
_MAX_PERCENT = 100
_HUNDRED = Decimal(_MAX_PERCENT)
#: What a quote total is floored to: a cent, coarser than any Spot pair's
#: quote precision, so a total the panel offers is one the exchange takes.
QUOTE_STEP = Decimal("0.01")


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
    #: `EPIC-028O` — the app's per-order notional limit; `None` when it
    #: could not be read, which leaves the maxima uncapped by it.
    notional_limit: Decimal | None = None


@dataclass(frozen=True)
class SideInput:
    """What the user typed on one side. `None` is an empty or unreadable
    field."""

    price: Decimal | None = None
    quantity: Decimal | None = None
    #: `EPIC-028O` — a stop-limit's trigger price.
    stop_price: Decimal | None = None
    #: `EPIC-028O` — what a quote-sized market buy spends.
    total: Decimal | None = None


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
    #: `EPIC-028O` — whether the side's amount is a quote total (a Spot
    #: market buy) rather than a base quantity.
    sized_by_quote: bool = False
    #: `EPIC-028O` — the most quote a side sized by quote may spend; `None`
    #: on a side sized by base quantity, or when the balance is unknown.
    max_total: Decimal | None = None

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
    if side is EntrySide.BUY and order_type is OrderType.MARKET:
        return _spot_quote_buy_figures(entry, context, last_price)
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
    max_quantity = _capped_by_limit(max_quantity, price, step, context.notional_limit)
    quantity = entry.quantity
    total: Decimal | None = None
    fee: Decimal | None = None
    if quantity is not None and quantity > 0 and price is not None and price > 0:
        total = quantity * price
        fee = estimated_fee(quantity, price, fee_rate)
    problem = _stop_problem(side, order_type, entry, last_price) or _first_problem(
        side, order_type, entry, context, price, max_quantity
    )
    return SideFigures(
        price=price,
        available=available,
        available_asset=asset,
        max_quantity=max_quantity,
        total=total,
        fee=fee,
        problem=problem,
    )


def _spot_quote_buy_figures(
    entry: SideInput, context: OrderEntryContext, last_price: Decimal | None
) -> SideFigures:
    """A Spot market buy, sized by the quote it spends (`quoteOrderQty`).
    The base quantity it buys is the exchange's to decide; the figures show
    it at the last price."""
    available = context.available_quote
    max_total = (
        _ROUNDING.round_quantity_down(available, QUOTE_STEP)
        if available is not None
        else None
    )
    if max_total is not None and context.notional_limit is not None:
        max_total = min(max_total, context.notional_limit)
    priced = last_price is not None and last_price > 0
    step = context.terms.rules.step_size_for(OrderType.MARKET)
    max_quantity = (
        _ROUNDING.round_quantity_down(max_total / last_price, step)
        if max_total is not None and priced and last_price is not None
        else None
    )
    spend = entry.total
    fee = (
        spend * context.terms.commission.taker
        if spend is not None and spend > 0
        else None
    )
    return SideFigures(
        price=last_price,
        available=available,
        available_asset=context.quote_asset,
        max_quantity=max_quantity,
        total=spend if spend is not None and spend > 0 else None,
        fee=fee,
        problem=_quote_buy_problem(spend, context, priced, max_total),
        sized_by_quote=True,
        max_total=max_total,
    )


def _capped_by_limit(
    max_quantity: Decimal | None,
    price: Decimal | None,
    step: Decimal,
    limit: Decimal | None,
) -> Decimal | None:
    """`max_quantity`, lowered to what `limit` allows at `price`."""
    if max_quantity is None or limit is None or price is None or price <= 0:
        return max_quantity
    return min(max_quantity, _ROUNDING.round_quantity_down(limit / price, step))


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
    limit = context.notional_limit
    if limit is not None and rounded * price > limit:
        return _over_limit(limit, context.quote_asset)
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


def _quote_buy_problem(
    spend: Decimal | None,
    context: OrderEntryContext,
    priced: bool,
    max_total: Decimal | None,
) -> str | None:
    if not priced:
        return "No market price yet. Wait for live data."
    if spend is None or spend <= 0:
        return "Enter a total."
    if spend < context.terms.rules.min_notional:
        return (
            f"The order is worth less than the minimum of "
            f"{context.terms.rules.min_notional} {context.quote_asset}."
        )
    limit = context.notional_limit
    if limit is not None and spend > limit:
        return _over_limit(limit, context.quote_asset)
    if max_total is None:
        return "The balance could not be read. Check the connection."
    if spend > max_total:
        return f"Not enough {context.quote_asset}: at most {max_total}."
    return None


def _stop_problem(
    side: EntrySide,
    order_type: OrderType,
    entry: SideInput,
    last_price: Decimal | None,
) -> str | None:
    """A stop-limit's own problems, before the limit order's: no stop, no
    last price to judge it by, or a stop already crossed."""
    if order_type is not OrderType.STOP_LIMIT:
        return None
    stop = entry.stop_price
    if stop is None or stop <= 0:
        return "Enter a stop price."
    if last_price is None or last_price <= 0:
        return "No market price yet. Wait for live data."
    order_side = OrderSide.BUY if side is EntrySide.BUY else OrderSide.SELL
    if (
        check_stop_trigger_side(order_side, stop, last_price)
        is StopPriceCheck.ON_TRIGGER_SIDE
    ):
        return None
    where = "above" if side is EntrySide.BUY else "below"
    return (
        f"A {side.value.lower()} stop must be {where} the last price "
        f"({last_price}); this one would trigger at once."
    )


def _over_limit(limit: Decimal, quote_asset: str) -> str:
    return (
        f"The order is worth more than the app's limit of {limit} {quote_asset} "
        "per order."
    )
