"""`EPIC-028I` — the figures a Futures order panel shows beside each side,
and the first thing that stops it, without Qt.

@details The Futures counterpart of `spot_side_figures`, sized by
`EPIC-028G`'s estimates so the panel and the estimates cannot disagree:
- **the maximum** is what the available balance pays (cost plus fee) within
  the leverage's notional cap; a market order also pays its open loss
  against the book (`futures_market_max_quantity`), and waits for the book
  when it could not be read. Every maximum is capped by the app's per-order
  limit, as on Spot;
- **reduce-only** sizes against the position it can reduce instead: a buy
  reduces a short, a sell a long, and there is nothing to reduce when flat;
- **cost** is Binance's (initial margin plus open loss); **liquidation** is
  the estimate for the position the order would open, never the exchange's
  figure (`LiquidationPriceEstimate`);
- **TP/SL** levels must sit on their side of the order's price
  (`protection_problem`), and a reduce-only order has no new position to
  protect.

Which side a button finally sends, and whether it reduces, is still
`manual_order_intent_for()`'s, read from the real position at submit time.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.futures_order_estimates import (
    FuturesOrderTerms,
    assuming_price,
    book_open_loss,
    futures_market_max_quantity,
    futures_max_quantity,
    futures_order_cost,
    futures_order_fee,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.liquidation_estimate import (
    LiquidationPriceEstimate,
    LiquidationTerms,
    estimated_liquidation_price,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_quantity_rounding_policy import (
    OrderQuantityRoundingPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.position_side import (
    PositionSide,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.protective_levels import (
    ProtectiveLevels,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.protective_orders import (
    protection_problem,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.futures_entry_context import (
    FuturesEntryContext,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_rules import (
    EntrySide,
    OrderEntryContext,
    SideFigures,
    SideInput,
    capped_by_limit,
    over_limit_text,
    sent_price,
    stop_problem,
)

_ROUNDING = OrderQuantityRoundingPolicy()
_ORDER_SIDE = {EntrySide.BUY: OrderSide.BUY, EntrySide.SELL: OrderSide.SELL}


def futures_side_figures(
    side: EntrySide,
    order_type: OrderType,
    entry: SideInput,
    context: OrderEntryContext,
    last_price: Decimal | None,
) -> SideFigures:
    """@return One Futures side's figures and the first problem, if any."""
    futures = context.futures
    price = sent_price(
        side, last_price if order_type is OrderType.MARKET else entry.price, context
    )
    if futures is None:
        return _waiting(context, price, "Leverage and margin are still loading.")
    if last_price is None or last_price <= 0 or price is None or price <= 0:
        missing = (
            "No market price yet. Wait for live data."
            if order_type is OrderType.MARKET or last_price is None
            else "Enter a price."
        )
        return _waiting(context, price, missing)
    terms = FuturesOrderTerms(
        side=_ORDER_SIDE[side],
        order_price=None if order_type is OrderType.MARKET else price,
        last_price=last_price,
        mark_price=futures.mark_price,
        leverage=futures.setting.leverage,
        fee_rate=context.terms.commission.taker,
        notional_headroom=futures.notional_headroom,
    )
    step = context.terms.rules.step_size_for(order_type)
    book = _book_price(side, futures)
    if entry.reduce_only:
        max_quantity: Decimal | None = _reducible(side, futures, step)
    else:
        max_quantity = _max_opening(context, terms, book, step)
    max_quantity = capped_by_limit(max_quantity, price, step, context.notional_limit)
    quantity = entry.quantity if entry.quantity and entry.quantity > 0 else None
    cost = fee = total = None
    liquidation = None
    if quantity is not None:
        total = quantity * price
        fee = futures_order_fee(quantity, terms)
        cost = Decimal(0) if entry.reduce_only else _cost(quantity, terms, book)
        if not entry.reduce_only:
            liquidation = _liquidation(side, quantity, price, terms, futures)
    problem = stop_problem(side, order_type, entry, last_price) or _first_problem(
        _SideCheck(side, order_type, entry, context, price, max_quantity)
    )
    return SideFigures(
        price=price,
        available=context.available_quote,
        available_asset=context.quote_asset,
        max_quantity=max_quantity,
        total=total,
        fee=fee,
        problem=problem,
        cost=cost,
        liquidation=liquidation,
    )


def _waiting(
    context: OrderEntryContext, price: Decimal | None, problem: str
) -> SideFigures:
    return SideFigures(
        price=price,
        available=context.available_quote,
        available_asset=context.quote_asset,
        max_quantity=None,
        total=None,
        fee=None,
        problem=problem,
    )


def _book_price(side: EntrySide, futures: FuturesEntryContext) -> Decimal | None:
    """The price a market order on `side` meets: the best ask for a buy,
    the best bid for a sell; `None` when that side of the book is empty or
    unread."""
    book = futures.book
    if book is None:
        return None
    if side is EntrySide.BUY:
        return book.ask_price if book.has_ask else None
    return book.bid_price if book.has_bid else None


def _max_opening(
    context: OrderEntryContext,
    terms: FuturesOrderTerms,
    book: Decimal | None,
    step: Decimal,
) -> Decimal | None:
    available = context.available_quote
    if available is None:
        return None
    if terms.order_price is not None:
        return futures_max_quantity(available, terms, step)
    if book is None:
        return None
    return futures_market_max_quantity(available, terms, book, step)


def _reducible(side: EntrySide, futures: FuturesEntryContext, step: Decimal) -> Decimal:
    """What a reduce-only order on `side` can close: a buy reduces a short,
    a sell a long."""
    amount = futures.position_amount
    reduces = amount < 0 if side is EntrySide.BUY else amount > 0
    return _ROUNDING.round_quantity_down(abs(amount), step) if reduces else Decimal(0)


def _cost(quantity: Decimal, terms: FuturesOrderTerms, book: Decimal | None) -> Decimal:
    cost = futures_order_cost(quantity, terms)
    if terms.order_price is None and book is not None:
        cost += book_open_loss(quantity, terms.side, terms.mark_price, book)
    return cost


def _liquidation(
    side: EntrySide,
    quantity: Decimal,
    price: Decimal,
    terms: FuturesOrderTerms,
    futures: FuturesEntryContext,
) -> LiquidationPriceEstimate | None:
    """The estimate for the position this order opens on its own: isolated,
    its initial margin; cross, the wallet balance (`liquidation_estimate.py`
    says why cross reads optimistic)."""
    if futures.setting.margin_type is MarginType.ISOLATED:
        margin: Decimal | None = quantity * assuming_price(terms) / terms.leverage
    else:
        margin = futures.wallet_balance
    if margin is None:
        return None
    bracket = futures.brackets.bracket_for(quantity * price)
    return estimated_liquidation_price(
        LiquidationTerms(
            side=PositionSide.LONG if side is EntrySide.BUY else PositionSide.SHORT,
            quantity=quantity,
            entry_price=price,
            margin=margin,
            maintenance_margin_rate=bracket.maintenance_margin_rate,
            maintenance_amount=bracket.maintenance_amount,
        )
    )


@dataclass(frozen=True)
class _SideCheck:
    """One side's order, as the problem checks read it."""

    side: EntrySide
    order_type: OrderType
    entry: SideInput
    context: OrderEntryContext
    price: Decimal
    max_quantity: Decimal | None


def _first_problem(check: _SideCheck) -> str | None:
    rules = check.context.terms.rules
    quantity = check.entry.quantity
    if quantity is None or quantity <= 0:
        return "Enter an amount."
    step = rules.step_size_for(check.order_type)
    rounded = _ROUNDING.round_quantity_down(quantity, step)
    if rounded <= 0:
        return f"The amount is below one lot of {step} {check.context.base_asset}."
    if not check.entry.reduce_only and rounded * check.price < rules.min_notional:
        return (
            f"The order is worth less than the minimum of "
            f"{rules.min_notional} {check.context.quote_asset}."
        )
    limit = check.context.notional_limit
    if limit is not None and rounded * check.price > limit:
        return over_limit_text(limit, check.context.quote_asset)
    return _size_problem(check, rounded) or _protection_problem(
        check.side, check.entry, check.price
    )


def _size_problem(check: _SideCheck, rounded: Decimal) -> str | None:
    maximum = check.max_quantity
    if check.entry.reduce_only:
        held = "short" if check.side is EntrySide.BUY else "long"
        if not maximum:
            return f"No {held} position to reduce."
        if rounded > maximum:
            return f"Reduce-only: the {held} position is {maximum}."
        return None
    if maximum is None:
        if check.context.available_quote is None:
            return "The balance could not be read. Check the connection."
        return "The order book could not be read yet."
    if rounded > maximum:
        return (
            f"Not enough margin: at most {maximum} {check.context.base_asset} "
            "at this leverage."
        )
    return None


def _protection_problem(
    side: EntrySide, entry: SideInput, price: Decimal
) -> str | None:
    if entry.take_profit is None and entry.stop_loss is None:
        return None
    if entry.reduce_only:
        return "TP/SL protects a new position; turn off reduce-only."
    return protection_problem(
        _ORDER_SIDE[side], price, ProtectiveLevels(entry.take_profit, entry.stop_loss)
    )
