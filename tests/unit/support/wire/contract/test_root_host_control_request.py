"""`EPIC-047A` — an operator's request to the running host crosses the wire equal, for every action."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    HostControlAction,
    HostControlRequest,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.contract.round_trip import (
    assert_full_leaves_no_field_empty,
    assert_round_trips,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.contract.samples_core import (
    add_request,
    full_request,
    minimal_request,
)

ROOT = "sew.host-control-request/1"


@pytest.mark.parametrize("value", [full_request(), add_request()], ids=["full", "add"])
def test_a_full_instance_round_trips(value: HostControlRequest) -> None:
    assert_round_trips(ROOT, value)


def test_a_minimal_instance_round_trips() -> None:
    assert_round_trips(ROOT, minimal_request())


@pytest.mark.parametrize(
    "action", list(HostControlAction), ids=lambda a: a.name.lower()
)
def test_every_action_round_trips_as_its_member(action: HostControlAction) -> None:
    assert_round_trips(ROOT, HostControlRequest(action, "b-0001"))


def test_the_full_instances_set_every_field() -> None:
    assert_full_leaves_no_field_empty([full_request()])
