"""The contract suite for `IVenueTradingPorts` (HLD §10.3).

The guarantees another module relies on when it arms a strategy or trades on
one venue:
- a served venue answers with its own bundle, the same instance every time,
  stamped with that venue;
- `enabled()` never lists `DISABLED`;
- a venue that is not served is refused with `VenueNotEnabledError`, never
  answered with some other venue's ports;
- `primary()` is the bundle of the first enabled venue.

A subclass provides `impl`, serving Futures first and Spot second.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    VenueNotEnabledError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class VenueTradingPortsContract:
    """Inherit this and provide `impl` serving Futures, then Spot."""

    @pytest.fixture
    def impl(self) -> IVenueTradingPorts:
        raise NotImplementedError(
            "a VenueTradingPortsContract subclass must provide an `impl` fixture"
        )

    def test_each_served_venue_answers_with_its_own_bundle(
        self, impl: IVenueTradingPorts
    ) -> None:
        futures = impl.get(TradingVenue.FUTURES_TESTNET)
        spot = impl.get(TradingVenue.SPOT_TESTNET)

        assert futures.venue is TradingVenue.FUTURES_TESTNET
        assert spot.venue is TradingVenue.SPOT_TESTNET
        assert futures.trading_session is not spot.trading_session

    def test_a_venue_answers_with_the_same_bundle_every_time(
        self, impl: IVenueTradingPorts
    ) -> None:
        assert impl.get(TradingVenue.SPOT_TESTNET) is impl.get(
            TradingVenue.SPOT_TESTNET
        )

    def test_enabled_lists_the_served_venues_in_order(
        self, impl: IVenueTradingPorts
    ) -> None:
        assert impl.enabled() == (
            TradingVenue.FUTURES_TESTNET,
            TradingVenue.SPOT_TESTNET,
        )

    def test_an_unserved_venue_is_refused(self, impl: IVenueTradingPorts) -> None:
        with pytest.raises(VenueNotEnabledError):
            impl.get(TradingVenue.DISABLED)

    def test_primary_is_the_first_enabled_venue(self, impl: IVenueTradingPorts) -> None:
        assert impl.primary() is impl.get(TradingVenue.FUTURES_TESTNET)
