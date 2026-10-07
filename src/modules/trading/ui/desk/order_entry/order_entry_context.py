"""What the order panel read off the exchange for its symbol, as one value
(`EPIC-028H`), split out of `OrderEntryPresenter` (`EPIC-034C`: the presenter
sits at the 400-line ceiling)."""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_entry_terms import (
    OrderEntryTerms,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_rules import (
    OrderEntryContext,
)


def context_from_reads(
    quote: str,
    symbol: str,
    terms: OrderEntryTerms,
    status: ExchangeConnectionStatus,
    notional_limit: Decimal,
) -> OrderEntryContext:
    """The panel's context from the terms and the connection read: the quote
    the account can spend, and the base it can sell (zero when it holds none)."""
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
