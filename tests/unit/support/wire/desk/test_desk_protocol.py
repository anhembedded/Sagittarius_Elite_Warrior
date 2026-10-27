"""`EPIC-047D` - the desktop's half of the conversation, against the real `BridgeSession`, on a clock that is a number."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace

import pytest
from Sagittarius_Elite_Warrior.src.support.wire.bridge.bridge_protocol import (
    IDLE_WATCHDOG_S,
)
from Sagittarius_Elite_Warrior.src.support.wire.bridge.bridge_session import (
    BridgeSession,
    SessionPorts,
)
from Sagittarius_Elite_Warrior.src.support.wire.desk.contracts.link_errors import (
    BridgeRefusedError,
    LinkError,
    LinkLostError,
    VersionDifferenceError,
)
from Sagittarius_Elite_Warrior.src.support.wire.desk.desk_protocol import (
    DeskProtocol,
    IDeskListener,
    LinkTimings,
)
from Sagittarius_Elite_Warrior.src.support.wire.link_handshake import Hello
from Sagittarius_Elite_Warrior.tests.unit.support.wire.bridge.bridge_world import (
    ROOTS,
    VERSION,
    FakeBots,
    FakeDoor,
    FakeFacts,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.contract.samples_bots import (
    full_bot,
    minimal_bot,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.desk.desk_world import (
    DESK_HELLO,
)


@dataclass
class Heard(IDeskListener):
    ready: LinkTimings | None = None
    results: dict[int, dict[str, object]] = field(default_factory=dict)
    errors: dict[int, tuple[str, str]] = field(default_factory=dict)
    events: list[dict[str, object]] = field(default_factory=list)
    closed: list[LinkError | None] = field(default_factory=list)

    def on_ready(self, timings: LinkTimings) -> None:
        self.ready = timings

    def on_result(self, call_id: int, data: dict[str, object]) -> None:
        self.results[call_id] = data

    def on_call_error(self, call_id: int, code: str, message: str) -> None:
        self.errors[call_id] = (code, message)

    def on_event(self, event: dict[str, object]) -> None:
        self.events.append(event)

    def on_closed(self, reason: LinkError | None) -> None:
        self.closed.append(reason)


class Pair:
    """A desktop protocol and a real bridge session, joined by two lists and a clock the test moves."""

    def __init__(
        self, *, bridge_hello: Hello | None = None, desk_hello: Hello = DESK_HELLO
    ) -> None:
        self.now = 100.0
        self.bots = FakeBots(full_bot(), minimal_bot())
        self.to_bridge: list[str] = []
        self.to_desk: list[str] = []
        self.heard = Heard()
        self.bridge = BridgeSession(
            ROOTS,
            VERSION,
            SessionPorts(self.bots, FakeFacts(), FakeDoor()),
            lambda m: self.to_desk.append(json.dumps(m)),
            lambda work: work(),
        )
        if bridge_hello is not None:
            self.bridge._hello = bridge_hello
        self.desk = DeskProtocol(
            desk_hello, lambda m: self.to_bridge.append(json.dumps(m)), self.heard
        )
        self.bridge.begin(self.now)
        self.desk.begin(self.now)

    def settle(self) -> None:
        while self.to_desk or self.to_bridge:
            while self.to_desk:
                self.desk.feed(self.to_desk.pop(0), self.now)
            while self.to_bridge:
                self.bridge.feed(self.to_bridge.pop(0), self.now)

    def advance(self, seconds: float, *, bridge_hears_desk: bool = True) -> None:
        self.now += seconds
        self.desk.tick(self.now)
        if bridge_hears_desk:
            self.settle()
            self.bridge.tick(self.now)
            self.settle()


def test_the_same_build_is_welcomed_and_the_desk_learns_the_bridges_cadence() -> None:
    pair = Pair()
    pair.settle()

    assert pair.desk.is_ready
    assert pair.heard.ready == LinkTimings(2.0, IDLE_WATCHDOG_S)
    assert pair.heard.ready.ping_every_s == pytest.approx(IDLE_WATCHDOG_S / 3)


def test_a_host_of_another_build_is_refused_in_words_and_the_desk_sends_no_hello() -> (
    None
):
    other = Hello(DESK_HELLO.protocol, "0.0.1", dict(DESK_HELLO.root_hashes))
    pair = Pair(bridge_hello=other)
    pair.settle()

    assert pair.desk.is_closed
    refusal = pair.heard.closed[0]
    assert isinstance(refusal, VersionDifferenceError)
    assert "0.0.1" in refusal.words and VERSION in refusal.words
    assert pair.to_bridge == []
    assert pair.bots.asked == 0


def test_a_wire_form_that_differs_names_the_root() -> None:
    roots = dict(DESK_HELLO.root_hashes)
    name = next(iter(roots))
    roots[name] = "0" * 16
    pair = Pair(bridge_hello=Hello(DESK_HELLO.protocol, VERSION, roots))
    pair.settle()

    refusal = pair.heard.closed[0]
    assert isinstance(refusal, VersionDifferenceError)
    assert name in refusal.words


def test_a_bridge_that_refuses_the_desk_after_the_hello_is_reported_with_its_words() -> (
    None
):
    pair = Pair()
    pair.settle()
    pair.desk.feed(
        json.dumps(
            {
                "type": "refused",
                "reason": "internal",
                "differs": [],
                "words": "it broke",
            }
        ),
        pair.now,
    )

    refusal = pair.heard.closed[0]
    assert isinstance(refusal, BridgeRefusedError)
    assert refusal.reason == "internal" and "it broke" in refusal.words


def test_a_line_that_is_not_json_closes_the_link_with_a_sentence() -> None:
    pair = Pair()
    pair.desk.feed("garbage", pair.now)

    assert isinstance(pair.heard.closed[0], BridgeRefusedError)


def test_a_call_gets_its_result_by_id_and_a_bad_one_gets_its_error() -> None:
    pair = Pair()
    pair.settle()

    snapshot = pair.desk.call("snapshot", {}, pair.now)
    refused = pair.desk.call("nonsense", {}, pair.now)
    pair.settle()

    assert set(pair.heard.results[snapshot]) >= {"seq", "list", "revisions", "facts"}
    assert pair.heard.errors[refused][0] == "unknown_method"
    assert pair.desk.pending_ids == frozenset()


def test_an_answer_to_a_call_nobody_made_is_ignored() -> None:
    pair = Pair()
    pair.settle()

    pair.desk.feed(json.dumps({"type": "result", "id": 99, "data": {}}), pair.now)

    assert pair.heard.results == {} and not pair.desk.is_closed


def test_a_call_before_the_greeting_is_done_is_a_lost_link_not_a_send() -> None:
    pair = Pair()

    with pytest.raises(LinkLostError):
        pair.desk.call("snapshot", {}, pair.now)

    assert pair.to_bridge == []


def test_events_reach_the_listener_once_subscribed() -> None:
    pair = Pair()
    pair.settle()
    pair.desk.call("snapshot", {}, pair.now)
    pair.desk.call("subscribe", {}, pair.now)
    pair.settle()

    pair.bots.put(full_bot())
    pair.advance(0.2)

    assert [e["kind"] for e in pair.heard.events] == ["bot"]


def test_a_live_link_outlives_the_bridges_watchdog_on_pings_alone() -> None:
    pair = Pair()
    pair.settle()

    for _ in range(
        30
    ):  # 30 s with no call at all: only the desk's pings reach the bridge
        pair.advance(1.0)

    assert pair.bridge.exit_code is None
    assert not pair.desk.is_closed and pair.heard.closed == []


def test_no_ping_before_a_third_and_one_after() -> None:
    pair = Pair()
    pair.settle()
    sent_before = len(pair.to_bridge)

    pair.advance(1.9, bridge_hears_desk=False)
    assert len(pair.to_bridge) == sent_before

    pair.advance(0.2, bridge_hears_desk=False)
    assert [json.loads(m)["type"] for m in pair.to_bridge[sent_before:]] == ["ping"]


def test_a_half_open_link_is_noticed_after_a_watchdog_of_silence() -> None:
    pair = Pair()
    pair.settle()

    pair.advance(IDLE_WATCHDOG_S - 0.1, bridge_hears_desk=False)
    assert not pair.desk.is_closed
    pair.advance(0.2, bridge_hears_desk=False)

    lost = pair.heard.closed[0]
    assert isinstance(lost, LinkLostError)
    assert "half open" in lost.words


def test_any_line_from_the_host_resets_the_silence_clock() -> None:
    pair = Pair()
    pair.settle()
    for _ in range(4):
        pair.advance(IDLE_WATCHDOG_S - 1.0, bridge_hears_desk=False)
        pair.desk.feed(json.dumps({"type": "pong"}), pair.now)

    assert not pair.desk.is_closed


def test_a_greeting_that_never_finishes_ends_the_attempt() -> None:
    pair = Pair()
    # the bridge's hello is never delivered
    pair.to_desk.clear()

    pair.advance(11.0, bridge_hears_desk=False)

    assert isinstance(pair.heard.closed[0], LinkLostError)


def test_a_transport_that_says_the_pipe_is_gone_closes_once() -> None:
    pair = Pair()
    pair.settle()

    pair.desk.lost(LinkLostError("reset"))
    pair.desk.lost(LinkLostError("reset again"))
    pair.desk.close()

    assert len(pair.heard.closed) == 1


def test_a_changed_protocol_version_is_a_difference_too() -> None:
    other = replace(DESK_HELLO, protocol="sew.link/9")
    pair = Pair(bridge_hello=other)
    pair.settle()

    assert isinstance(pair.heard.closed[0], VersionDifferenceError)
