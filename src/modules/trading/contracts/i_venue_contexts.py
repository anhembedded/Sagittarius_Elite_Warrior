"""`EPIC-028A` — the one place a caller learns which venues are live and gets
the ports of the venue it acts on (ADR D2)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_context import (
    VenueContext,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class VenueNotEnabledError(LookupError):
    """A caller asked for a venue the configuration does not enable — a
    wiring bug, never a condition to fall back from silently
    (`code/errors.md` #6)."""

    def __init__(self, venue: TradingVenue, enabled: tuple[TradingVenue, ...]) -> None:
        enabled_names = ", ".join(v.value for v in enabled) or "none"
        super().__init__(
            f"Trading venue {venue.value!r} is not enabled (enabled: {enabled_names})."
        )
        self.venue = venue


class IVenueContexts(ABC):
    """Registry of the enabled venues' `VenueContext`s."""

    @abstractmethod
    def enabled(self) -> tuple[TradingVenue, ...]:
        """The enabled venues, in configuration order; empty when trading is
        off. Never contains `TradingVenue.DISABLED`."""

    @abstractmethod
    def get(self, venue: TradingVenue) -> VenueContext:
        """The context of `venue`, the same instance on every call.

        `TradingVenue.DISABLED` is served only while nothing is enabled,
        when it is the primary venue (`primary()`): a command addressed to
        the process's own read-only venue still gets that venue's adapters,
        and its handler refuses it through
        `TradingVenue.supports_order_submission`, as it always has.
        @raise VenueNotEnabledError `venue` is neither enabled nor the
        primary venue."""

    @abstractmethod
    def primary(self) -> VenueContext:
        """The context the single-venue callers still use until `EPIC-028B`
        names a venue on every command: the first enabled venue, or
        `TradingVenue.DISABLED`'s read-only context when none is enabled
        (the same Futures-shaped adapters the process has always bound while
        trading is off)."""
