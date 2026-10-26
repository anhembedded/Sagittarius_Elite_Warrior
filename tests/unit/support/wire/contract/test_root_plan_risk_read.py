"""`EPIC-047A` — a plan-risk read, facts or the reason there are none, crosses the wire as the member it was."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.tests.unit.support.wire.contract.round_trip import (
    assert_full_leaves_no_field_empty,
    assert_round_trips,
    assert_union_root_covers_every_member,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.contract.samples_bots import (
    full_plan_risk,
    unavailable_plan_risk,
)

ROOT = "sew.plan-risk-read/1"

FULL = [full_plan_risk()]
MINIMAL = [unavailable_plan_risk()]


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
