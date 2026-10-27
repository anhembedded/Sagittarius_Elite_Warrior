"""`EPIC-047C` - the bridge speaks first, refuses a different build before it reads a file, and says why."""

from __future__ import annotations

import json

import pytest
from Sagittarius_Elite_Warrior.src.support.wire.bridge.bridge_protocol import (
    EXIT_PROTOCOL,
    EXIT_REFUSED,
    HEARTBEAT_S,
    HELLO_TIMEOUT_S,
    IDLE_WATCHDOG_S,
)
from Sagittarius_Elite_Warrior.src.support.wire.link_handshake import (
    PROTOCOL,
    Hello,
    hello_of,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.bridge.bridge_world import (
    ROOTS,
    VERSION,
    Desk,
)


def test_the_bridge_says_hello_first_with_its_build_and_its_timings() -> None:
    desk = Desk()

    desk.session.begin(desk.now)

    (hello,) = desk.out
    assert hello["type"] == "hello"
    assert hello["protocol"] == PROTOCOL
    assert hello["app_version"] == VERSION
    assert hello["roots"] == ROOTS.root_hashes()
    assert (hello["heartbeat_s"], hello["idle_watchdog_s"]) == (
        HEARTBEAT_S,
        IDLE_WATCHDOG_S,
    )
    assert pytest.approx(IDLE_WATCHDOG_S) == HEARTBEAT_S * 3


def test_the_same_build_gets_a_welcome_and_the_session_goes_on() -> None:
    desk = Desk()

    desk.greet()

    assert [m["type"] for m in desk.out] == ["hello", "welcome"]
    assert desk.session.exit_code is None


def test_a_different_build_is_refused_in_words_and_the_bridge_exits_3() -> None:
    desk = Desk()

    desk.greet(Hello(PROTOCOL, "0.0.1", hello_of(ROOTS, VERSION).root_hashes))

    (refusal,) = desk.sent("refused")
    assert refusal["reason"] == "incompatible"
    assert refusal["differs"] == ["app_version"]
    assert "sudo sew-update" in str(refusal["words"])
    assert desk.session.exit_code == EXIT_REFUSED


def test_a_different_wire_form_is_refused_and_names_the_root_that_differs() -> None:
    desk = Desk()
    hashes = dict(hello_of(ROOTS, VERSION).root_hashes)
    hashes["sew.bot-list/1"] = "0" * 16

    desk.greet(Hello(PROTOCOL, VERSION, hashes))

    (refusal,) = desk.sent("refused")
    assert refusal["differs"] == ["wire:sew.bot-list/1"]
    assert desk.session.exit_code == EXIT_REFUSED


def test_a_refused_desk_causes_no_read_of_any_file() -> None:
    """Before any read (`EPIC-047A`'s deferral): the bots' files and the facts file are untouched."""
    desk = Desk()

    desk.greet(Hello(PROTOCOL, "0.0.1", hello_of(ROOTS, VERSION).root_hashes))

    assert (desk.bots.asked, desk.facts.asked) == (0, 0)
    assert desk.door.sent == []


def test_a_welcomed_desk_is_the_first_to_cause_a_read() -> None:
    desk = Desk()

    desk.greet()

    assert desk.bots.asked > 0
    assert desk.facts.asked > 0


def test_nothing_is_said_after_a_refusal() -> None:
    desk = Desk()
    desk.greet(Hello(PROTOCOL, "0.0.1", hello_of(ROOTS, VERSION).root_hashes))
    said = len(desk.out)

    desk.call("snapshot")
    desk.advance(1.0)

    assert len(desk.out) == said


@pytest.mark.parametrize(
    "first",
    [
        {"type": "call", "id": 1, "method": "snapshot"},
        {"type": "hello"},
        {"type": "hello", "protocol": PROTOCOL, "app_version": "x"},
        {"type": "hello", "protocol": 3, "app_version": "x", "roots": {}},
        {"type": "hello", "protocol": PROTOCOL, "app_version": "x", "roots": []},
        {
            "type": "hello",
            "protocol": PROTOCOL,
            "app_version": "x",
            "roots": {"a": "b"},
        },
    ],
    ids=[
        "a-call",
        "no-body",
        "no-roots",
        "protocol-not-text",
        "roots-not-a-map",
        "bad-name",
    ],
)
def test_a_first_line_that_is_not_a_hello_ends_the_session_with_status_4(
    first: dict[str, object],
) -> None:
    desk = Desk()
    desk.session.begin(desk.now)

    desk.feed(first)

    assert desk.session.exit_code == EXIT_PROTOCOL
    assert desk.sent("refused")[0]["reason"] in {"no_hello", "bad_hello"}
    assert (desk.bots.asked, desk.facts.asked) == (0, 0)


@pytest.mark.parametrize(
    "line", ["", "not json", "[1, 2]", "42"], ids=["empty", "text", "array", "number"]
)
def test_a_line_that_is_not_a_json_object_ends_the_session_with_status_4(
    line: str,
) -> None:
    desk = Desk()
    desk.session.begin(desk.now)

    desk.session.feed(line, desk.now)

    assert desk.session.exit_code == EXIT_PROTOCOL
    assert desk.sent("refused")[0]["reason"] == "bad_json"


def test_a_desk_that_never_says_hello_is_let_go_after_the_hello_timeout() -> None:
    desk = Desk()
    desk.session.begin(desk.now)

    desk.advance(HELLO_TIMEOUT_S - 0.1)
    assert desk.session.exit_code is None
    desk.advance(0.2)

    assert desk.session.exit_code == EXIT_PROTOCOL
    assert desk.sent("refused")[0]["reason"] == "no_hello"
    assert (desk.bots.asked, desk.facts.asked) == (0, 0)


def test_the_hello_and_the_welcome_are_single_lines_of_json_text() -> None:
    desk = Desk()
    desk.greet()

    for message in desk.out:
        assert "\n" not in json.dumps(message)
