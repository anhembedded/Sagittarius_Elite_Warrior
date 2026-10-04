"""`EPIC-029E` — the numbers a bot's orders are held to, read from trading.

The symbol's filters and the account's maker and taker rates
(`IOrderEntryTerms.terms_for`), trading's per-order notional cap as configured
now (`order_notional_limit`, ADR D21: never a literal), and the most orders an
owner budget may keep open (`OwnerBudgetCaps`, ADR O1).
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    ExchangeTerms,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_order_entry_terms import (
    IOrderEntryTerms,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerBudgetCaps,
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
    )
