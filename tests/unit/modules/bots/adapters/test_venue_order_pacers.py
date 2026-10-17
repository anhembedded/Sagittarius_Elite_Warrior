"""`EPIC-029J` J1b — one order pacer per venue, so the bots of a venue keep the spacing together.

The owner budget's spacing is per owner (trading refuses a bot's order sent too soon after its
own); the exchange's `ORDERS` limit is per account (`EPIC-029A` notes), so what must hold at the
account is that the venue's orders, whichever bot sends them, keep the spacing.
"""

from __future__ import annotations

from datetime import timedelta

from Sagittarius_Elite_Warrior.src.modules.bots.adapters.venue_order_pacers import (
    VenueOrderPacers,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

SPACING = timedelta(milliseconds=250)
SPOT = TradingVenue.SPOT_TESTNET
FUTURES = TradingVenue.FUTURES_TESTNET


def test_two_bots_of_one_venue_get_the_same_pacer() -> None:
    pacers = VenueOrderPacers()

    assert pacers.of(FUTURES, SPACING) is pacers.of(FUTURES, SPACING)


def test_two_venues_do_not_pace_each_other() -> None:
    pacers = VenueOrderPacers()

    assert pacers.of(FUTURES, SPACING) is not pacers.of(SPOT, SPACING)


def test_a_different_spacing_is_a_different_pacer() -> None:
    pacers = VenueOrderPacers()

    assert pacers.of(FUTURES, SPACING) is not pacers.of(FUTURES, SPACING * 2)
