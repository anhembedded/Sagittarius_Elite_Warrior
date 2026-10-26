"""`EPIC-047C` — `IVenueKeyStates` over each venue's stored key provider (`stored_credentials_provider`).

A provider is built for each question and not kept: `MainnetCredentialsProvider` reads the stores
once and keeps the answer for the life of the process, so a kept one would go on saying "no key"
after the enrolment script saved one, until the host restarted. The cost is one read of the secret
stores per enabled venue per look (the host-facts publisher looks every `FACTS_POLL_SECONDS`), a
permission-checked file or a systemd credential on the VPS.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.composition.shared_venue_inputs import (
    SharedVenueInputs,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.venue_assembly import (
    stored_credentials_provider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    VenueNotEnabledError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_key_states import (
    IVenueKeyStates,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class StoredVenueKeyStates(IVenueKeyStates):
    def __init__(
        self, enabled: tuple[TradingVenue, ...], shared: SharedVenueInputs
    ) -> None:
        self._enabled = enabled
        self._shared = shared

    def key_saved(self, venue: TradingVenue) -> bool:
        if venue not in self._enabled:
            raise VenueNotEnabledError(venue, self._enabled)
        return (
            stored_credentials_provider(venue, self._shared).resolve().credentials
            is not None
        )
