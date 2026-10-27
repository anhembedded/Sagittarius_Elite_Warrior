"""`IVenueKeyStates`'s fake: the venues it is given have a key, the others are enabled without one."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    VenueNotEnabledError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_key_states import (
    IVenueKeyStates,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class FakeVenueKeyStates(IVenueKeyStates):
    def __init__(
        self,
        enabled: tuple[TradingVenue, ...],
        with_key: tuple[TradingVenue, ...] = (),
    ) -> None:
        self._enabled = enabled
        self._with_key = frozenset(with_key)

    def key_saved(self, venue: TradingVenue) -> bool:
        if venue not in self._enabled:
            raise VenueNotEnabledError(venue, self._enabled)
        return venue in self._with_key
