"""`EPIC-035R`, `BOT-174` — the ladder a Resume proposes, as one pure function.

A resume from HALTED lays no opening buy (ADR D13, §3.4): the SELL side is sized
to the inventory the bot holds and the BUY side shares only the capital that
inventory leaves. The executor proposes this plan (`GridResumeSequence`) and the
readiness rules judge what it needs from the account (`grid_needs.py`), so the
screen's judgement and the proposal are the same plan, not two copies of the sizing.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    ExchangeTerms,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_ladder import (
    buys_within_capital,
    resized_for_inventory,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import (
    GridPlan,
    plan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_reactions import (
    LadderRules,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerInventory,
)


def resume_plan(
    params: GridParams,
    terms: ExchangeTerms,
    price: Decimal,
    inventory: OwnerInventory,
) -> GridPlan:
    """The plan at `price` over `inventory`: SELLs sized to what is held, BUYs
    sized to the capital it leaves."""
    sells = resized_for_inventory(
        plan(params, terms, price), inventory.quantity, terms.min_notional
    )
    left = params.capital_quote - inventory.cost
    return buys_within_capital(
        sells, left, LadderRules(terms.step_size, terms.min_notional)
    )
