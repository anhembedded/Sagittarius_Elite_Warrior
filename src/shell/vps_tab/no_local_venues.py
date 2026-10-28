"""`EPIC-047E` — the venues the VPS tab serves on this computer: none.

@details The Bots screen's strategy commands (Arm, Disarm) act on the venues `IVenueTradingPorts` serves, through this computer's own
trading. The VPS tab's strategies belong to the host (they travel as host verbs, `EPIC-047E` PR 3), so its container answers this
port with no venue at all: the commands are built over nothing and stay disabled, instead of arming a strategy here by mistake
on a tab that says VPS.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    VenueNotEnabledError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_trading_ports import (
    VenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class NoLocalVenues(IVenueTradingPorts):
    def enabled(self) -> tuple[TradingVenue, ...]:
        return ()

    def get(self, venue: TradingVenue) -> VenueTradingPorts:
        raise VenueNotEnabledError(venue, ())

    def primary(self) -> VenueTradingPorts:
        raise VenueNotEnabledError(TradingVenue.DISABLED, ())
