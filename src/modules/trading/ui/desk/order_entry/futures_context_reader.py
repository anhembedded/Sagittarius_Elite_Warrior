"""`EPIC-028I` — reads a Futures symbol's sizing context for the order
panel: leverage and margin mode, brackets, mark price, book and position.

@details Runs on the panel's load worker, beside the terms and the account
read. A venue without leverage (Spot) answers `NotApplicable` to the first
read and gets no Futures context. A book that could not be read is `None`:
the limit maximum does not need it and the market maximum waits for it;
every other failure fails the load, which the panel names.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_summary import (
    FuturesAccountSummary,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.best_bid_ask import (
    BestBidAsk,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_snapshot import (
    IAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_order_entry_terms import (
    IOrderEntryTerms,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.market_price_unavailable_error import (
    MarketPriceUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.not_applicable import (
    NotApplicable,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.futures_entry_context import (
    FuturesEntryContext,
)


def read_futures_context(
    terms: IOrderEntryTerms,
    account: IAccountSnapshot,
    symbol: str,
    status: ExchangeConnectionStatus,
) -> FuturesEntryContext | None:
    """@return `symbol`'s Futures reads, or `None` on a venue without
    leverage."""
    setting = terms.futures_setting_for(symbol)
    if setting is NotApplicable.ON_THIS_VENUE:
        return None
    brackets = terms.leverage_brackets_for(symbol)
    mark = terms.mark_price_for(symbol)
    if brackets is NotApplicable.ON_THIS_VENUE or mark is NotApplicable.ON_THIS_VENUE:
        return None
    position = next((p for p in account.open_positions() if p.symbol == symbol), None)
    summary = status.summary if status.reachable else None
    return FuturesEntryContext(
        setting=setting,
        brackets=brackets,
        mark_price=mark.mark_price,
        book=_book_or_none(terms, symbol),
        position_amount=position.position_amt if position else Decimal(0),
        wallet_balance=(
            summary.wallet_balance
            if isinstance(summary, FuturesAccountSummary)
            else None
        ),
    )


def _book_or_none(terms: IOrderEntryTerms, symbol: str) -> BestBidAsk | None:
    try:
        return terms.best_bid_ask_for(symbol)
    except MarketPriceUnavailableError:
        return None
