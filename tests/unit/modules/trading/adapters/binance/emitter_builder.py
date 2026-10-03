"""A venue's `VenueEventEmitter` over a bus, with an empty set of owner
books: what a stream test needs when no owner budget is in play."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.venue_event_emitter import (
    VenueEventEmitter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_books import (
    OwnerBooks,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.interfaces.i_event_bus import IEventBus


def venue_emitter(event_bus: IEventBus, venue: TradingVenue) -> VenueEventEmitter:
    return VenueEventEmitter(event_bus, venue, OwnerBooks())
