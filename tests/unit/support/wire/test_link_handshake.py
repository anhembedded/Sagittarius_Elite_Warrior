"""`EPIC-047A` — the handshake refuses a build difference in words, naming what differs (R6, D6).

The bridge answers `refused` and exits before any read; the desktop shows the words. There is no
read-only mode across versions in v1.
"""

from __future__ import annotations

from dataclasses import make_dataclass
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.wire_root import WireRoot
from Sagittarius_Elite_Warrior.src.support.wire.link_handshake import (
    PROTOCOL,
    Hello,
    hello_of,
    judge,
)
from Sagittarius_Elite_Warrior.src.support.wire.wire_errors import WireDecodeError
from Sagittarius_Elite_Warrior.src.support.wire.wire_roots import WireRoots


def _roots(*names: str, price_type: type = Decimal) -> WireRoots:
    return WireRoots(
        [
            WireRoot(n, make_dataclass(f"T{i}", [("price", price_type)], frozen=True))
            for i, n in enumerate(names)
        ]
    )


def test_the_same_build_is_accepted() -> None:
    hello = hello_of(_roots("sew.test-a/1", "sew.test-b/1"), "2026.10.26")
    assert (
        judge(hello, hello_of(_roots("sew.test-a/1", "sew.test-b/1"), "2026.10.26"))
        is None
    )


def test_a_different_app_version_is_refused_with_both_builds_and_the_remedy() -> None:
    host = hello_of(_roots("sew.test-a/1"), "2026.10.20")
    desk = hello_of(_roots("sew.test-a/1"), "2026.10.26")
    refusal = judge(host, desk)
    assert refusal is not None
    assert refusal.differs == ("app_version",)
    assert refusal.words == (
        "the VPS host runs build 2026.10.20, this desktop runs 2026.10.26: run `sudo sew-update`"
    )


def test_the_same_version_with_a_changed_wire_form_names_the_root_that_changed() -> (
    None
):
    host = hello_of(_roots("sew.test-a/1", "sew.test-b/1"), "dev")
    desk = hello_of(_roots("sew.test-a/1", "sew.test-b/1", price_type=str), "dev")
    refusal = judge(host, desk)
    assert refusal is not None
    assert refusal.differs == ("wire:sew.test-a/1", "wire:sew.test-b/1")
    assert "sew.test-a/1" in refusal.words
    assert "host runs build dev" in refusal.words


def test_a_root_only_one_side_has_is_named_with_the_side() -> None:
    host = hello_of(_roots("sew.test-a/1"), "dev")
    desk = hello_of(_roots("sew.test-a/1", "sew.test-b/1"), "dev")
    refusal = judge(host, desk)
    assert refusal is not None
    assert refusal.differs == ("wire:sew.test-b/1",)
    assert "the host lacks sew.test-b/1" in refusal.words
    reverse = judge(desk, host)
    assert reverse is not None
    assert "this desktop lacks sew.test-b/1" in reverse.words


def test_a_different_protocol_is_refused_first() -> None:
    host = Hello("sew.link/0", "dev", {})
    desk = hello_of(_roots("sew.test-a/1"), "dev")
    refusal = judge(host, desk)
    assert refusal is not None
    assert refusal.differs[0] == "protocol"


def test_a_hello_crosses_the_wire_and_back() -> None:
    hello = hello_of(_roots("sew.test-a/1"), "2026.10.26")
    assert hello.protocol == PROTOCOL
    assert Hello.from_wire(hello.to_wire()) == hello


@pytest.mark.parametrize(
    "doc",
    [
        [],
        {"protocol": PROTOCOL, "app_version": "x"},
        {"protocol": 1, "app_version": "x", "roots": {}},
        {"protocol": PROTOCOL, "app_version": "x", "roots": {"sew.test-a/1": 5}},
        {"protocol": PROTOCOL, "app_version": "x", "roots": {}, "note": "y"},
    ],
    ids=["list", "no-roots", "protocol-number", "hash-number", "extra-key"],
)
def test_a_malformed_hello_is_a_decode_error(doc: object) -> None:
    with pytest.raises(WireDecodeError):
        Hello.from_wire(doc)


def test_the_refusal_is_a_message_the_desktop_can_read() -> None:
    refusal = judge(
        hello_of(_roots("sew.test-a/1"), "1"), hello_of(_roots("sew.test-a/1"), "2")
    )
    assert refusal is not None
    assert refusal.to_wire() == {
        "type": "refused",
        "reason": "incompatible",
        "differs": ["app_version"],
        "words": refusal.words,
    }
