"""`EPIC-029F`, `EPIC-034H` — the venue's numbers a plan is judged against.

The symbol's filters and fees and the current price, read as the start check
reads them, so the screen's planner, the readiness query and Start judge a plan
against the same numbers. A venue that cannot be read answers a sentence naming
why, never a partial set.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_exchange_terms import (
    exchange_terms_for,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    ExchangeTerms,
    MarketView,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.commission_rate_unavailable_error import (
    CommissionRateUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.market_price_unavailable_error import (
    MarketPriceUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerBudgetCaps,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_rules_unavailable_error import (
    SymbolRulesUnavailableError,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

type PlannerNumbers = tuple[ExchangeTerms, MarketView]


def read_planner_numbers(
    ports: IVenueTradingPorts,
    caps: OwnerBudgetCaps,
    venue: TradingVenue,
    symbol: str,
) -> PlannerNumbers | str:
    """The terms and the mid price, or the sentence that says why not."""
    if venue.market_type is not MarketType.SPOT or venue not in ports.enabled():
        return f"{venue.display_name} is not an enabled Spot venue"
    entry_terms = ports.get(venue).order_entry_terms
    try:
        terms = exchange_terms_for(entry_terms, symbol, caps)
        book = entry_terms.best_bid_ask_for(symbol)
    except (
        SymbolRulesUnavailableError,
        CommissionRateUnavailableError,
        MarketPriceUnavailableError,
    ) as exc:
        return f"{symbol} on {venue.display_name}: {exc}"
    price: Decimal = (book.bid_price + book.ask_price) / 2
    return terms, MarketView(price)
