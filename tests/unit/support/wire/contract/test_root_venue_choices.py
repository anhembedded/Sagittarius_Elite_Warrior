"""`EPIC-048B` — the venues a bot may be on cross the wire equal: a venue, its connection words and a
closed reason, and never a key (the record has no field that could hold one)."""

from __future__ import annotations

import dataclasses

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_choice import (
    KEY_SAVED,
    NOT_ENABLED,
    VenueChoice,
    VenueChoices,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.contract.round_trip import (
    assert_full_leaves_no_field_empty,
    assert_round_trips,
)

ROOT = "sew.venue-choices/1"

FULL = [
    VenueChoices(
        (
            VenueChoice(TradingVenue.SPOT_TESTNET, KEY_SAVED, "closed by this build"),
            VenueChoice(TradingVenue.FUTURES_MAINNET, NOT_ENABLED, "not offered yet"),
        )
    )
]
MINIMAL = [VenueChoices()]


@pytest.mark.parametrize("value", FULL, ids=lambda v: "full-" + type(v).__name__)
def test_a_full_instance_round_trips(value: object) -> None:
    assert_round_trips(ROOT, value)


@pytest.mark.parametrize("value", MINIMAL, ids=lambda v: "minimal-" + type(v).__name__)
def test_a_minimal_instance_round_trips(value: object) -> None:
    assert_round_trips(ROOT, value)


def test_the_full_instances_set_every_field() -> None:
    assert_full_leaves_no_field_empty(FULL)


def test_a_venue_choice_carries_a_venue_and_words_never_a_key() -> None:
    assert [field.name for field in dataclasses.fields(VenueChoice)] == [
        "venue",
        "connection",
        "closed_reason",
    ]
