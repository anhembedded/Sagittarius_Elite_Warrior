"""`EPIC-047A` — the host's Run facts and its budget caps, a duration included, cross the wire equal."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.tests.unit.support.wire.contract.round_trip import (
    assert_full_leaves_no_field_empty,
    assert_round_trips,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.contract.samples_bots import (
    full_run_facts,
    minimal_run_facts,
)

ROOT = "sew.bot-run-facts/1"

FULL = [full_run_facts()]
MINIMAL = [minimal_run_facts()]


@pytest.mark.parametrize("value", FULL, ids=lambda v: "full-" + type(v).__name__)
def test_a_full_instance_round_trips(value: object) -> None:
    assert_round_trips(ROOT, value)


@pytest.mark.parametrize("value", MINIMAL, ids=lambda v: "minimal-" + type(v).__name__)
def test_a_minimal_instance_round_trips(value: object) -> None:
    assert_round_trips(ROOT, value)


def test_the_full_instances_set_every_field() -> None:
    assert_full_leaves_no_field_empty(FULL)
