"""`IVenueProfiles` over the profile table (`EPIC-039A`)."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_venue_profiles import (
    IVenueProfiles,
    VenueTradesNoMarketError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    VenueProfile,
    venue_profile_of,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class VenueProfilesByMarket(IVenueProfiles):
    """Reads no market itself: it asks `venue_profile_of`, the one place that does."""

    def for_venue(self, venue: TradingVenue) -> VenueProfile:
        profile = venue_profile_of(venue)
        if profile is None:
            raise VenueTradesNoMarketError(f"{venue.value} trades no market")
        return profile
