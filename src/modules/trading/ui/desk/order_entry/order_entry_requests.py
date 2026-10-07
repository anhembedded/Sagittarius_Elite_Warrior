"""`EPIC-028H` — what the order panel builds from what it read and what was
typed, without Qt: the context a symbol's terms and the account make, and the
`OrderRequest` a side asks for. Moved out of `OrderEntryPresenter` by
`BOT-169` (it outgrew 400 lines); unchanged.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_entry_terms import (
    OrderEntryTerms,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_request import (
    OrderRequest,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_profile import (
    DeskProfile,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_rules import (
    EntrySide,
    OrderEntryContext,
    SideFigures,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_view_model import (
    OrderEntryViewModel,
)

_ORDER_SIDE = {EntrySide.BUY: OrderSide.BUY, EntrySide.SELL: OrderSide.SELL}


def order_entry_context_for(
    profile: DeskProfile,
    symbol: str,
    terms: OrderEntryTerms,
    status: ExchangeConnectionStatus,
    notional_limit: Decimal,
) -> OrderEntryContext:
    quote = profile.quote_asset
    base = symbol.removesuffix(quote)
    summary = status.summary if status.reachable else None
    holdings = status.holdings if status.reachable else None
    free_base: Decimal | None = None
    if holdings is not None:
        held = next((h for h in holdings if h.asset == base), None)
        free_base = held.free if held is not None else Decimal(0)
    return OrderEntryContext(
        symbol=symbol,
        base_asset=base,
        quote_asset=quote,
        terms=terms,
        available_quote=summary.available_balance if summary else None,
        free_base=free_base,
        notional_limit=notional_limit,
    )


def order_request_for(
    vm: OrderEntryViewModel, side: EntrySide, figures: SideFigures, price: Decimal
) -> OrderRequest:
    """The order a side asks for: a stop-limit carries its stop and the
    last price it is judged against; a side sized by quote carries its
    total, and its quantity is only the estimate at `price`. The
    reduce-only box is read here, on the UI thread, as the user asked
    (the review of PR 307): the box stays enabled while the order is out."""
    entry = vm.entry(side)
    order_type = vm.order_type
    is_stop = order_type is OrderType.STOP_LIMIT
    quote = entry.total if figures.sized_by_quote else None
    quantity = quote / price if quote is not None else entry.quantity
    resting = order_type in (OrderType.LIMIT, OrderType.STOP_LIMIT)
    return OrderRequest(
        symbol=vm.order_symbol,
        side=_ORDER_SIDE[side],
        order_type=order_type,
        quantity=quantity or Decimal(0),
        reference_price=price,
        stop_price=entry.stop_price if is_stop else None,
        last_price=vm.last_price if is_stop else None,
        quote_quantity=quote,
        time_in_force=vm.options.time_in_force if resting else None,
        reduce_only=vm.options.reduce_only,
    )
