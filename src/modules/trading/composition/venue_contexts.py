"""`EPIC-028A` — `IVenueContexts`, backed by one `VenueAssembly` per venue."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.modules.trading.composition.venue_assembly import (
    VenueAssembly,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
    VenueNotEnabledError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_context import (
    VenueContext,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

logger = logging.getLogger("App.TradingVenues")


class VenueContexts(IVenueContexts):
    """@details Also hands the composition root each venue's
    `VenueAssembly` (`assembly()`), so a test of the wiring can see one
    venue's parts together — one object per venue, whichever door a caller
    comes in by."""

    def __init__(
        self,
        enabled: tuple[TradingVenue, ...],
        build_assembly: Callable[[TradingVenue], VenueAssembly],
    ) -> None:
        self._enabled = enabled
        self._build_assembly = build_assembly
        self._assemblies: dict[TradingVenue, VenueAssembly] = {}
        self._lock = threading.Lock()
        logger.info(
            "Trading venues enabled: %s; primary venue: %s.",
            [v.value for v in enabled] or "none",
            self.primary_venue.value,
        )

    @property
    def primary_venue(self) -> TradingVenue:
        return self._enabled[0] if self._enabled else TradingVenue.DISABLED

    def enabled(self) -> tuple[TradingVenue, ...]:
        return self._enabled

    def get(self, venue: TradingVenue) -> VenueContext:
        return self.assembly(venue).context

    def primary(self) -> VenueContext:
        return self.assembly(self.primary_venue).context

    def assembly(self, venue: TradingVenue) -> VenueAssembly:
        """The composition root's own access to one venue's parts. Accepts
        `DISABLED` only as the primary venue while nothing is enabled."""
        if venue not in self._enabled and venue is not self.primary_venue:
            raise VenueNotEnabledError(venue, self._enabled)
        with self._lock:
            existing = self._assemblies.get(venue)
            if existing is None:
                existing = self._build_assembly(venue)
                self._assemblies[venue] = existing
            return existing
