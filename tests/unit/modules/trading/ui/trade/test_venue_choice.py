"""`EPIC-033I` — the venue the Trade mode trades is remembered between runs,
and a remembered venue no longer enabled gives way to one that is."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.ui.trade.venue_choice import (
    VenueChoice,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

FUTURES = TradingVenue.FUTURES_TESTNET
SPOT = TradingVenue.SPOT_TESTNET


def test_the_first_enabled_venue_is_chosen_until_the_person_chooses(qapp) -> None:
    assert VenueChoice((FUTURES, SPOT), None).current is FUTURES
    assert VenueChoice((SPOT,), None).current is SPOT
    assert VenueChoice((), None).current is None


def test_a_remembered_venue_is_chosen_again(qapp) -> None:
    first = VenueChoice((FUTURES, SPOT), None)
    first.restore_state({"venue": SPOT.value})
    saved = first.capture_state()

    second = VenueChoice((FUTURES, SPOT), None)
    second.restore_state(saved)

    assert saved == {"venue": SPOT.value}
    assert second.current is SPOT


def test_a_remembered_venue_no_longer_enabled_gives_way(qapp) -> None:
    choice = VenueChoice((SPOT,), None)

    choice.restore_state({"venue": FUTURES.value})

    assert choice.current is SPOT
