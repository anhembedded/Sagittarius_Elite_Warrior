"""`EPIC-028B` — how another context or a screen reaches one venue's
published trading ports (ADR D2/D3)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_trading_ports import (
    VenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class IVenueTradingPorts(ABC):
    """Registry of each served venue's `VenueTradingPorts`."""

    @abstractmethod
    def enabled(self) -> tuple[TradingVenue, ...]:
        """The enabled venues, in configuration order; empty when trading is
        off. Never contains `TradingVenue.DISABLED`."""

    @abstractmethod
    def get(self, venue: TradingVenue) -> VenueTradingPorts:
        """The ports of `venue`, the same instance on every call. Serves
        `TradingVenue.DISABLED` only while it is the primary venue, the rule
        `IVenueContexts.get()` states.
        @raise VenueNotEnabledError `venue` is neither enabled nor the
        primary venue."""

    @abstractmethod
    def primary(self) -> VenueTradingPorts:
        """The ports the single Trading screen and Dev Board use until
        `EPIC-028K`/`028L` give each venue its own desk: the first enabled
        venue, or `TradingVenue.DISABLED`'s when none is enabled."""
