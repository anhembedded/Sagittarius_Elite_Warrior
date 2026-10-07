"""`EPIC-034F` — everything a Grid's checks may read, computed once.

Held apart from `grid_checks.py` so the account's constraints
(`grid_account_checks.py`) and the table that classifies every constraint
(`grid_constraints.py`) can name it without importing each other.
"""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    AccountView,
    ExchangeTerms,
    MarketView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_derived import (
    GridDerived,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import GridPlan
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
)


@dataclass(frozen=True, slots=True)
class GridCheckInputs:
    """Everything a check may read, computed once."""

    params: GridParams
    plan: GridPlan
    derived: GridDerived
    terms: ExchangeTerms
    market: MarketView
    thresholds: GridThresholds
    #: What the Connect step read; `None` until it did.
    account: AccountView | None = None
