"""`EPIC-047C` review round 1 - what the desktop sends, or a port does, that nobody planned for, is a word and a status."""

from __future__ import annotations

import json

import pytest
from Sagittarius_Elite_Warrior.src.support.wire.bridge.bridge_protocol import (
    EXIT_INTERNAL,
    EXIT_PROTOCOL,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.bridge.bridge_world import (
    REQUEST_ID,
    ROOTS,
    Desk,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.contract.samples_core import (
    minimal_request,
)

REQUEST_ROOT = "sew.host-control-request/1"


def test_a_line_nested_past_the_parsers_recursion_limit_is_a_protocol_violation_not_a_crash() -> (
    None
):
    """A line of 200 000 `[` is 200 KB, far inside the line bound, and `json.loads` raises
    `RecursionError` on it (review round 1, finding 1)."""
    desk = Desk()
    desk.session.begin(desk.now)

    desk.session.feed("[" * 200_000, desk.now)

    assert desk.session.exit_code == EXIT_PROTOCOL
    assert desk.sent("refused")[0]["reason"] == "bad_json"


def test_a_wait_too_large_for_a_float_is_refused_not_a_crash() -> None:
    desk = Desk()
    desk.greet()

    call = desk.call(
        "command",
        request_id=REQUEST_ID,
        request=ROOTS.encode(REQUEST_ROOT, minimal_request()),
        wait_s=10**400,
    )

    assert desk.error_of(call)["code"] == "bad_command"
    assert desk.session.exit_code is None
    assert desk.door.sent == []


class _BreaksOnThePoll(Desk):
    def __init__(self) -> None:
        super().__init__()
        self.broken = False

    def break_the_directory(self) -> None:
        def stamps() -> dict[str, tuple[int, ...]]:
            raise RuntimeError("the directory vanished mid-look")

        self.bots.stamps = stamps  # type: ignore[method-assign]


def test_an_unforeseen_failure_in_a_port_ends_the_session_with_its_own_status_and_a_word() -> (
    None
):
    desk = _BreaksOnThePoll()
    desk.greet()
    desk.break_the_directory()

    desk.advance(1.0)

    assert desk.session.exit_code == EXIT_INTERNAL
    refusal = desk.sent("refused")[-1]
    assert refusal["reason"] == "internal"
    assert "directory vanished" not in json.dumps(refusal)


@pytest.mark.parametrize("seconds", [-1, 31, float("inf"), 10**400])
def test_a_wait_out_of_range_is_refused(seconds: float) -> None:
    desk = Desk()
    desk.greet()

    call = desk.call(
        "command",
        request_id=REQUEST_ID,
        request=ROOTS.encode(REQUEST_ROOT, minimal_request()),
        wait_s=seconds,
    )

    assert desk.error_of(call)["code"] == "bad_command"
