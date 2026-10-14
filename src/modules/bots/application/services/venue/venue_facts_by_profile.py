"""`EPIC-039E` — the readiness facts of a bot's venue, read by the adapter its profile names.

`IVenueFacts` for a caller that does not know whether its venue is Spot or Futures: the
profile's `exposure_kind` picks the adapter (`ExchangeFactsReader` for an inventory venue,
`FuturesFactsReader` for a position venue). A venue that trades no market is an
`ExchangeUnavailable` with the reason, never an empty snapshot.
"""

from __future__ import annotations

from collections.abc import Mapping

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.exchange_facts import (
    ExchangeUnavailable,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.futures_facts import (
    VenueSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_venue_facts import (
    IVenueFacts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_venue_profiles import (
    IVenueProfiles,
    VenueTradesNoMarketError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    ExposureKind,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import Bot


class VenueFactsByProfile(IVenueFacts):
    def __init__(
        self, profiles: IVenueProfiles, by_exposure: Mapping[ExposureKind, IVenueFacts]
    ) -> None:
        self._profiles = profiles
        self._by_exposure = by_exposure

    def read(self, bot: Bot) -> VenueSnapshot:
        venue = bot.definition.venue
        try:
            profile = self._profiles.for_venue(venue)
        except VenueTradesNoMarketError:
            return ExchangeUnavailable(f"{venue.display_name} trades no market")
        return self._by_exposure[profile.exposure_kind].read(bot)
