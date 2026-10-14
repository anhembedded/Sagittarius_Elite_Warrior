"""`EPIC-039H` — the owner budget a Grid asks trading for, per venue profile.

@details Trading judges a budgeted owner's orders against the budget it registered
(`OwnerBudget`): on Spot in BUY quote and inventory at cost, on a position venue in position
notional and margin (`FuturesLimits`, `EPIC-039D`). The bot declares which; this port is the one
place that does, so the start's preconditions, the registrations of a running bot and a resume
all ask for the same budget and none of them names a market.

Plausible extensions, each a local change: a Cross-margin budget reads the other positions'
margin (one more adapter); a daily-loss cap is one more field of `OwnerBudget` filled here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerBudget,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class IGridBudgets(ABC):
    @abstractmethod
    def budget_of(
        self, venue: TradingVenue, symbol: str, params: GridParams
    ) -> OwnerBudget:
        """The budget a Grid of `params` on `symbol` of `venue` registers with trading."""
