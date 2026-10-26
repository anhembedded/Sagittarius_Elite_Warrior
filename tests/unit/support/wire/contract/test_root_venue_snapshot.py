"""`EPIC-047A` — what the exchange says, in each of its states and for each market, crosses as the member it was."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.tests.unit.support.wire.contract.round_trip import (
    assert_full_leaves_no_field_empty,
    assert_round_trips,
    assert_union_root_covers_every_member,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.contract.samples_bots import (
    checking,
    loaded_exchange_full,
    loaded_exchange_minimal,
    loaded_futures_full,
    loaded_futures_minimal,
    unavailable,
)

ROOT = "sew.venue-snapshot/1"

FULL = [loaded_exchange_full(), loaded_futures_full()]
MINIMAL = [
    checking(),
    unavailable(),
    loaded_exchange_minimal(),
    loaded_futures_minimal(),
]


@pytest.mark.parametrize("value", FULL, ids=lambda v: "full-" + type(v).__name__)
def test_a_full_instance_round_trips(value: object) -> None:
    assert_round_trips(ROOT, value)


@pytest.mark.parametrize("value", MINIMAL, ids=lambda v: "minimal-" + type(v).__name__)
def test_a_minimal_instance_round_trips(value: object) -> None:
    assert_round_trips(ROOT, value)


def test_the_full_instances_set_every_field() -> None:
    assert_full_leaves_no_field_empty(FULL)


def test_the_instances_cover_every_member_of_the_union() -> None:
    assert_union_root_covers_every_member(ROOT, [*FULL, *MINIMAL])
