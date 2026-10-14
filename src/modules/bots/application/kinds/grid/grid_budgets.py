"""`EPIC-039H` — the owner budgets of a Grid, per venue profile (`IGridBudgets`).

· **Spot** (`grid_budget`, ADR D6): the capital in BUY quote and inventory at cost.
· **A position venue** (decision O2): `capital_quote` is the margin the user commits and the
  leverage multiplies it, so the position may be worth `capital × leverage`, and never more than
  the symbol's bracket allows at that leverage (`allowed_notional`). The margin is a second,
  independent ceiling (`FuturesLimits.committed_margin`). A bracket table that allows the leverage
  nowhere gives no ceiling of its own; the plan-time guard refuses such a ladder
  (`NOTIONAL_ABOVE_BRACKET`) before an order, and the readiness rule before the click.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_budget import (
    grid_budget,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue.symbol_brackets import (
    SymbolBrackets,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_grid_budgets import (
    IGridBudgets,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_venue_profiles import (
    IVenueProfiles,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    ExposureKind,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_notional_cap import (
    allowed_notional,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    FuturesLimits,
    OwnerBudget,
    OwnerBudgetCaps,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class SpotGridBudgets(IGridBudgets):
    def __init__(self, caps: OwnerBudgetCaps) -> None:
        self._caps = caps

    def budget_of(
        self, venue: TradingVenue, symbol: str, params: GridParams
    ) -> OwnerBudget:
        return grid_budget(params, self._caps)


class FuturesGridBudgets(IGridBudgets):
    def __init__(self, caps: OwnerBudgetCaps, brackets: SymbolBrackets) -> None:
        self._caps = caps
        self._brackets = brackets

    def budget_of(
        self, venue: TradingVenue, symbol: str, params: GridParams
    ) -> OwnerBudget:
        reach = params.capital_quote * params.leverage
        allowed = allowed_notional(self._brackets.get(venue, symbol), params.leverage)
        ceiling = min(reach, allowed) if allowed > 0 else reach
        limits = FuturesLimits(ceiling, params.leverage, params.capital_quote)
        return replace(grid_budget(params, self._caps), futures=limits)


class GridBudgetsByProfile(IGridBudgets):
    """Asks the adapter of the venue's exposure kind, as `VenueSettingsGates` does."""

    def __init__(
        self, profiles: IVenueProfiles, by_exposure: Mapping[ExposureKind, IGridBudgets]
    ) -> None:
        self._profiles = profiles
        self._by_exposure = by_exposure

    def budget_of(
        self, venue: TradingVenue, symbol: str, params: GridParams
    ) -> OwnerBudget:
        profile = self._profiles.for_venue(venue)
        return self._by_exposure[profile.exposure_kind].budget_of(venue, symbol, params)
