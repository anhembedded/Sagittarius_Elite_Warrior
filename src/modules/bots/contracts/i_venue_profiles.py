"""Ask what a venue allows (`EPIC-039A`): the injected form of `venue_profile_of`.

Application and UI code take this port; the `Bot` aggregate calls the pure function, because a
domain entity resolves no port. Both give the same answer (`VenueProfilesByMarket`).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    VenueProfile,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class VenueTradesNoMarketError(ValueError):
    """The venue (`DISABLED`) trades no market, so it has no profile."""


class IVenueProfiles(ABC):
    @abstractmethod
    def for_venue(self, venue: TradingVenue) -> VenueProfile:
        """@raise VenueTradesNoMarketError `venue` trades no market."""
