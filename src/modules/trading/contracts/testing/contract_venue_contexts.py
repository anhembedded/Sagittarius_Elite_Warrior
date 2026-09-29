"""The contract suite for `IVenueContexts` (HLD §10.3).

The guarantees a caller relies on when it acts on one venue:
- a served venue answers with its own context, the same instance every time,
  stamped with that venue and sharing no port with another venue;
- `enabled()` lists the served venues in configuration order, never
  `DISABLED`;
- a venue that is not served is refused with `VenueNotEnabledError`, never
  answered with another venue's ports;
- `primary()` is the first enabled venue's context; with nothing enabled it
  is `DISABLED`'s, and only then does `get(DISABLED)` answer.

A subclass provides `impl` (serving Futures, then Spot) and `impl_off`
(nothing enabled).
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
    VenueNotEnabledError,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

_FUTURES = TradingVenue.FUTURES_TESTNET
_SPOT = TradingVenue.SPOT_TESTNET


class VenueContextsContract:
    """Inherit this and provide `impl` and `impl_off`."""

    @pytest.fixture
    def impl(self) -> IVenueContexts:
        raise NotImplementedError(
            "a VenueContextsContract subclass must provide an `impl` fixture"
        )

    @pytest.fixture
    def impl_off(self) -> IVenueContexts:
        raise NotImplementedError(
            "a VenueContextsContract subclass must provide an `impl_off` fixture"
        )

    def test_each_served_venue_answers_with_its_own_ports(
        self, impl: IVenueContexts
    ) -> None:
        futures = impl.get(_FUTURES)
        spot = impl.get(_SPOT)

        assert futures.venue is _FUTURES
        assert spot.venue is _SPOT
        assert futures.account_reader is not spot.account_reader
        assert futures.metadata_provider is not spot.metadata_provider

    def test_a_venue_answers_with_the_same_context_every_time(
        self, impl: IVenueContexts
    ) -> None:
        assert impl.get(_SPOT) is impl.get(_SPOT)

    def test_enabled_lists_the_served_venues_in_order(
        self, impl: IVenueContexts
    ) -> None:
        assert impl.enabled() == (_FUTURES, _SPOT)

    def test_primary_is_the_first_enabled_venue(self, impl: IVenueContexts) -> None:
        assert impl.primary() is impl.get(_FUTURES)

    def test_disabled_is_refused_while_a_venue_is_enabled(
        self, impl: IVenueContexts
    ) -> None:
        with pytest.raises(VenueNotEnabledError):
            impl.get(TradingVenue.DISABLED)

    def test_with_nothing_enabled_only_disabled_is_served(
        self, impl_off: IVenueContexts
    ) -> None:
        assert impl_off.enabled() == ()
        assert impl_off.primary().venue is TradingVenue.DISABLED
        assert impl_off.get(TradingVenue.DISABLED) is impl_off.primary()
        with pytest.raises(VenueNotEnabledError):
            impl_off.get(_SPOT)
