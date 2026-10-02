"""`EPIC-028K` — how a desk reaches its own venue's live strategy.

@details Implemented by the strategy module (`trading` may not import it,
`DECISION_2026-09-17_strategy_ui_contributes_rather_than_being_imported.md`
§8), the same way `IStrategyArmingControl` is.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_strategy_controls import (
    VenueStrategyControls,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class IVenueStrategyControls(ABC):
    """Each served venue's `VenueStrategyControls`."""

    @abstractmethod
    def get(self, venue: TradingVenue) -> VenueStrategyControls:
        """The live strategy ports of `venue`, the same instance on every
        call.
        @raise VenueNotEnabledError `venue` is not served (the venue
        registries refuse first)."""
