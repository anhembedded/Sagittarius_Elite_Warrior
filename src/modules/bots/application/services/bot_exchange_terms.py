"""`EPIC-029E` — the numbers a bot's orders are held to, read from trading.

The symbol's filters and the account's maker and taker rates
(`IOrderEntryTerms.terms_for`), trading's per-order notional cap as configured
now (`order_notional_limit`, ADR D21: never a literal), and the most orders an
owner budget may keep open (`OwnerBudgetCaps`, ADR O1).
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    ExchangeTerms,
    PriceBand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_order_entry_terms import (
    IOrderEntryTerms,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerBudgetCaps,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    PercentPriceBand,
)


def exchange_terms_for(
    terms: IOrderEntryTerms, symbol: str, caps: OwnerBudgetCaps
) -> ExchangeTerms:
    entry = terms.terms_for(symbol)
    return ExchangeTerms(
        tick_size=entry.rules.tick_size,
        step_size=entry.rules.step_size,
        min_notional=entry.rules.min_notional,
        maker_fee=entry.commission.maker,
        taker_fee=entry.commission.taker,
        max_notional_per_order=terms.order_notional_limit(),
        max_open_orders=caps.max_open_orders,
        market_step_size=entry.rules.market_step_size,
        price_band=_price_band(entry.rules.price_band),
    )


def _price_band(band: PercentPriceBand | None) -> PriceBand | None:
    """`BUG-147` — trading's filter, as the bots module's own value."""
    if band is None:
        return None
    return PriceBand(
        buy_down=band.bid_down,
        buy_up=band.bid_up,
        sell_down=band.ask_down,
        sell_up=band.ask_up,
    )
