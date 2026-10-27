"""`EPIC-047C` — whether an enabled venue has an API key saved, asked without building the venue.

@details `IVenueContexts.get` builds a venue's adapters (clients, session factories, streams), so
a read-only fact about a venue nothing has used yet could not ask it on the real-money host. This
port answers from the stored key alone: nothing else of the venue is built and nothing leaves the
machine. It never returns a key, only whether one is saved.

@par Extension cases
  · another fact that needs the stored key only (its environment, its fingerprint) - one more
    method here; the real class reads the same provider.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class IVenueKeyStates(ABC):
    @abstractmethod
    def key_saved(self, venue: TradingVenue) -> bool:
        """True when `venue` has a stored key. @raise VenueNotEnabledError `venue` is not enabled."""
