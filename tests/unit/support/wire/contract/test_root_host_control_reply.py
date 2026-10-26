"""`EPIC-047A` — the host's answer to an operator's request crosses the wire equal, for every status."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    HostControlReply,
    HostControlStatus,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.contract.round_trip import (
    assert_full_leaves_no_field_empty,
    assert_round_trips,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.contract.samples_core import (
    full_reply,
    minimal_reply,
)

ROOT = "sew.host-control-reply/1"


def test_a_full_instance_round_trips() -> None:
    assert_round_trips(ROOT, full_reply())


def test_a_minimal_instance_round_trips() -> None:
    assert_round_trips(ROOT, minimal_reply())


@pytest.mark.parametrize(
    "status", list(HostControlStatus), ids=lambda s: s.name.lower()
)
def test_every_status_round_trips_as_its_member(status: HostControlStatus) -> None:
    assert_round_trips(ROOT, HostControlReply(status, "words"))


def test_the_full_instances_set_every_field() -> None:
    assert_full_leaves_no_field_empty([full_reply()])
