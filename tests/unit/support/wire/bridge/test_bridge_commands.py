"""`EPIC-047C` - a command crosses the bridge to the host's door under the desktop's id, and nowhere else."""

from __future__ import annotations

from dataclasses import replace

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    HostControlAction,
    HostControlReply,
    HostControlStatus,
)
from Sagittarius_Elite_Warrior.src.support.wire.bridge.bridge_protocol import (
    EXIT_PROTOCOL,
    MAX_COMMAND_WAIT_S,
    MAX_PENDING_COMMANDS,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.bridge.bridge_world import (
    REQUEST_ID,
    ROOTS,
    Desk,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.contract.samples_bots import (
    full_bot,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.contract.samples_core import (
    full_request,
    minimal_request,
)

REQUEST_ROOT = "sew.host-control-request/1"


def _greeted(desk: Desk | None = None) -> Desk:
    desk = desk or Desk()
    desk.greet()
    return desk


def test_a_command_reaches_the_door_with_the_desktops_id_its_request_and_its_wait() -> (
    None
):
    desk = _greeted()

    call = desk.call(
        "command",
        request_id=REQUEST_ID,
        request=ROOTS.encode(REQUEST_ROOT, full_request()),
        wait_s=7,
    )

    assert desk.door.sent == [(REQUEST_ID, full_request(), 7.0)]
    assert call == desk.sent("result")[0]["id"]


def test_the_reply_is_the_hosts_own_verdict_and_the_audit_reference() -> None:
    desk = _greeted()
    desk.door.reply = HostControlReply(
        HostControlStatus.REFUSED, "BTCUSDT is leased by b-0009", REQUEST_ID, "b-0001"
    )

    call = desk.call(
        "command",
        request_id=REQUEST_ID,
        request=ROOTS.encode(REQUEST_ROOT, minimal_request()),
    )

    reply = ROOTS.decode(desk.result_of(call)["reply"])
    assert reply == desk.door.reply
    assert reply.command_id == REQUEST_ID  # type: ignore[attr-defined]


def test_the_wait_defaults_and_is_bounded() -> None:
    desk = _greeted()
    request = ROOTS.encode(REQUEST_ROOT, minimal_request())

    desk.call("command", request_id=REQUEST_ID, request=request)
    over = desk.call(
        "command",
        request_id=REQUEST_ID,
        request=request,
        wait_s=MAX_COMMAND_WAIT_S + 1,
    )

    assert desk.door.sent[0][2] == 5.0
    assert len(desk.door.sent) == 1
    assert desk.error_of(over)["code"] == "bad_command"


def test_the_same_id_sent_twice_reaches_the_door_twice_and_the_door_does_the_work_once() -> (
    None
):
    """The bridge dedupes nothing: it is a new process after a reconnect. The id is the dedupe key and
    the host's audit is the memory (`DirectoryHostControl`, `ReplayingCommandDoor`)."""
    desk = _greeted()
    request = ROOTS.encode(REQUEST_ROOT, minimal_request())

    desk.call("command", request_id=REQUEST_ID, request=request)
    desk.call("command", request_id=REQUEST_ID, request=request)

    assert [sent[0] for sent in desk.door.sent] == [REQUEST_ID, REQUEST_ID]


@pytest.mark.parametrize(
    "params",
    [
        {"request": "x"},
        {"request_id": "", "request": "x"},
        {"request_id": "ABCDEF0123456789ABCDEF0123456789", "request": "x"},
        {"request_id": REQUEST_ID[:-1], "request": "x"},
        {"request_id": REQUEST_ID + "0", "request": "x"},
        {"request_id": 12, "request": "x"},
    ],
    ids=["missing", "empty", "upper-case", "short", "long", "not-text"],
)
def test_an_id_that_is_not_32_lowercase_hex_characters_is_refused_before_the_door(
    params: dict[str, object],
) -> None:
    desk = _greeted()

    call = desk.call("command", **params)

    assert desk.error_of(call)["code"] == "bad_command"
    assert desk.door.sent == []


@pytest.mark.parametrize(
    "request_message",
    [
        None,
        "stop",
        {},
        {"schema": "sew.bot-list/1", "data": {"bots": [], "refused": []}},
        {"schema": REQUEST_ROOT, "data": {"action": "reboot", "bot_id": "b"}},
        {"schema": REQUEST_ROOT, "data": {"action": "stop"}},
        {"schema": "sew.unknown/1", "data": {}},
    ],
    ids=[
        "none",
        "text",
        "empty",
        "another-root",
        "unknown-action",
        "missing-bot",
        "unknown-name",
    ],
)
def test_a_request_that_is_not_a_host_control_request_never_reaches_the_door(
    request_message: object,
) -> None:
    desk = _greeted()

    call = desk.call("command", request_id=REQUEST_ID, request=request_message)

    assert desk.error_of(call)["code"] == "bad_command"
    assert desk.door.sent == []


@pytest.mark.parametrize(
    "wait", ["5", None, True, float("inf")], ids=["text", "null", "bool", "inf"]
)
def test_a_wait_that_is_not_a_finite_number_is_refused(wait: object) -> None:
    desk = _greeted()

    call = desk.call(
        "command",
        request_id=REQUEST_ID,
        request=ROOTS.encode(REQUEST_ROOT, minimal_request()),
        wait_s=wait,
    )

    assert desk.error_of(call)["code"] == "bad_command"
    assert desk.door.sent == []


def test_a_failing_door_is_an_error_in_words_and_never_its_exception_text() -> None:
    desk = _greeted()
    desk.door.failure = RuntimeError("api_key=SECRET-LOOKING-VALUE failed")

    call = desk.call(
        "command",
        request_id=REQUEST_ID,
        request=ROOTS.encode(REQUEST_ROOT, minimal_request()),
    )

    error = desk.error_of(call)
    assert error["code"] == "door_failed"
    assert "SECRET-LOOKING-VALUE" not in str(error)


def test_commands_wait_on_their_own_threads_and_only_so_many_at_once() -> None:
    held: list[object] = []
    desk = Desk(spawn=held.append)
    desk.greet()
    request = ROOTS.encode(REQUEST_ROOT, minimal_request())

    calls = [
        desk.call("command", request_id=REQUEST_ID, request=request)
        for _ in range(MAX_PENDING_COMMANDS + 1)
    ]

    assert len(held) == MAX_PENDING_COMMANDS
    assert desk.error_of(calls[-1])["code"] == "busy"
    held[0]()  # type: ignore[operator]
    again = desk.call("command", request_id=REQUEST_ID, request=request)
    assert len(held) == MAX_PENDING_COMMANDS + 1
    assert [m["type"] for m in desk.out if m.get("id") == again] == []


def test_the_events_go_on_while_a_command_waits() -> None:
    held: list[object] = []
    desk = Desk(spawn=held.append)
    desk.greet()
    desk.call("subscribe")
    desk.call(
        "command",
        request_id=REQUEST_ID,
        request=ROOTS.encode(REQUEST_ROOT, minimal_request()),
    )
    desk.bots.put(replace(full_bot(), name="changed while the command waits"))
    desk.advance(0.1)

    assert len(desk.events("bot")) == 1
    assert desk.door.sent == []


def test_a_call_without_an_id_is_a_protocol_violation() -> None:
    desk = _greeted()

    desk.feed({"type": "call", "method": "snapshot"})

    assert desk.session.exit_code == EXIT_PROTOCOL


def test_an_unknown_method_is_an_error_and_the_session_goes_on() -> None:
    desk = _greeted()

    call = desk.call("reboot")

    assert desk.error_of(call)["code"] == "unknown_method"
    assert desk.session.exit_code is None


def test_the_command_verbs_the_bridge_forwards_are_the_hosts_not_a_list_of_its_own() -> (
    None
):
    """The bridge decodes a request into the host's own type and forwards it: a verb added to
    `HostControlAction` crosses with no change here (and the host's gate decides it)."""
    desk = _greeted()
    for action in HostControlAction:
        desk.call(
            "command",
            request_id=REQUEST_ID,
            request=ROOTS.encode(
                REQUEST_ROOT, type(minimal_request())(action, "b-0001")
            ),
        )

    assert [sent[1].action for sent in desk.door.sent] == list(HostControlAction)
