"""`EPIC-047D` - one live connection on its reader thread, against the real bridge: reads, events, a cut, a command.

No sleeps: a test waits on the link's own callbacks (`threading.Event`) with a bound.
"""

from __future__ import annotations

import threading

import pytest
from Sagittarius_Elite_Warrior.src.support.wire.desk.contracts.link_errors import (
    CallFailedError,
    CallTimedOutError,
    CommandInFlightLostError,
    HostUnreachableError,
    KeyRefusedError,
    LinkError,
    LinkLostError,
    VersionDifferenceError,
)
from Sagittarius_Elite_Warrior.src.support.wire.desk.desk_link import DeskLink
from Sagittarius_Elite_Warrior.src.support.wire.link_handshake import Hello
from Sagittarius_Elite_Warrior.tests.unit.support.wire.bridge.bridge_world import (
    ROOTS,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.contract.samples_core import (
    minimal_request,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.desk.desk_world import (
    DESK_HELLO,
    PROFILE,
    BridgeHost,
    BridgeTransport,
)

BOUND_S = 5.0
REQUEST_ID = "0123456789abcdef0123456789abcdef"
REQUEST_DOC = ROOTS.encode("sew.host-control-request/1", minimal_request())


class Rig:
    def __init__(self, transport: BridgeTransport, *, clock=None) -> None:
        self.events: list[dict[str, object]] = []
        self.got_event = threading.Event()
        self.closed = threading.Event()
        self.closed_with: list[LinkError | None] = []
        kwargs = {} if clock is None else {"monotonic": clock}
        self.link = DeskLink(
            transport,
            DESK_HELLO,
            on_event=self._event,
            on_closed=self._closed,
            **kwargs,
        )

    def _event(self, event: dict[str, object]) -> None:
        self.events.append(event)
        self.got_event.set()

    def _closed(self, reason: LinkError | None) -> None:
        self.closed_with.append(reason)
        self.closed.set()


@pytest.fixture
def host() -> BridgeHost:
    return BridgeHost()


def _up(host: BridgeHost, **kwargs) -> tuple[Rig, BridgeTransport]:
    transport = BridgeTransport(host)
    rig = Rig(transport, **kwargs)
    rig.link.connect(PROFILE)
    return rig, transport


def test_connect_returns_after_the_welcome_with_the_bridges_cadence(
    host: BridgeHost,
) -> None:
    transport = BridgeTransport(host)
    rig = Rig(transport)

    timings = rig.link.connect(PROFILE)

    assert timings.idle_watchdog_s > timings.heartbeat_s > 0
    assert rig.link.is_up
    rig.link.close()


def test_a_snapshot_then_a_subscription_then_a_write_arrives_as_an_event(
    host: BridgeHost,
) -> None:
    rig, _ = _up(host)
    snapshot = rig.link.call("snapshot")
    rig.link.call("subscribe")

    host.bots.put(host.bots.listing().value.bots[0])  # type: ignore[attr-defined]

    assert rig.got_event.wait(BOUND_S)
    assert set(snapshot["revisions"]) == {  # type: ignore[arg-type]
        b.bot_id
        for b in host.bots.listing().value.bots  # type: ignore[attr-defined]
    }
    assert rig.events[0]["kind"] == "bot"
    assert rig.link.data_as_of is not None
    rig.link.close()


def test_a_call_the_bridge_refuses_raises_call_failed_and_the_link_stays_up(
    host: BridgeHost,
) -> None:
    rig, _ = _up(host)

    with pytest.raises(CallFailedError) as refused:
        rig.link.call("no_such_method")

    assert refused.value.code == "unknown_method"
    assert rig.link.is_up
    rig.link.close()


def test_a_host_of_another_build_fails_connect_with_the_difference_in_words(
    host: BridgeHost,
) -> None:
    other = Hello(DESK_HELLO.protocol, "0.0.1", dict(DESK_HELLO.root_hashes))
    transport = BridgeTransport(host, bridge_hello=other)
    rig = Rig(transport)

    with pytest.raises(VersionDifferenceError) as refused:
        rig.link.connect(PROFILE)

    assert "0.0.1" in refused.value.words
    assert transport.closed
    assert host.bots.asked == 0


@pytest.mark.parametrize(
    "error",
    [
        KeyRefusedError("vps.example", "sew"),
        HostUnreachableError("vps.example", 22, "timed out"),
    ],
)
def test_a_typed_open_error_reaches_the_caller_unchanged(
    host: BridgeHost, error: LinkError
) -> None:
    transport = BridgeTransport(host)
    transport.fail_open(error)

    with pytest.raises(type(error)) as raised:
        Rig(transport).link.connect(PROFILE)

    assert raised.value is error


def test_a_cut_fails_a_pending_read_with_link_lost_and_tells_the_owner(
    host: BridgeHost,
) -> None:
    rig, transport = _up(host)

    transport.cut()

    assert rig.closed.wait(BOUND_S)
    assert isinstance(rig.closed_with[0], LinkLostError)
    with pytest.raises(LinkLostError):
        rig.link.call("snapshot")


def test_a_command_in_flight_at_the_cut_is_lost_by_id_and_never_sent_twice(
    host: BridgeHost,
) -> None:
    gate, at_the_door = threading.Event(), threading.Event()

    def held_door(*_args: object) -> object:
        at_the_door.set()
        gate.wait(BOUND_S)
        return host.door.reply

    host.door.send = held_door  # type: ignore[method-assign,assignment]
    rig, transport = _up(host)
    outcome: list[BaseException] = []

    def ask() -> None:
        try:
            rig.link.command(REQUEST_ID, REQUEST_DOC, 5.0)
        except BaseException as failure:  # noqa: BLE001 - the test collects what the caller sees
            outcome.append(failure)

    asking = threading.Thread(target=ask, daemon=True)
    asking.start()
    assert at_the_door.wait(
        BOUND_S
    )  # the command is on the wire and inside the host's door
    transport.cut()
    asking.join(timeout=BOUND_S)
    gate.set()

    assert isinstance(outcome[0], CommandInFlightLostError)
    assert outcome[0].request_id == REQUEST_ID
    assert len(transport.sent_of("call")) == 1


def test_a_half_open_link_is_closed_by_the_desks_own_clock(host: BridgeHost) -> None:
    now = [1000.0]
    rig, transport = _up(host, clock=lambda: now[0])

    transport.go_silent()
    now[0] += 60.0

    assert rig.closed.wait(BOUND_S)
    lost = rig.closed_with[0]
    assert isinstance(lost, LinkLostError) and "half open" in lost.words


def test_close_is_idempotent_and_ends_the_reader(host: BridgeHost) -> None:
    rig, transport = _up(host)

    rig.link.close()
    rig.link.close()

    assert transport.closed
    assert rig.closed.wait(BOUND_S)
    assert rig.closed_with == [None]


# -- review round 1 ------------------------------------------------------------------------


def test_a_transport_whose_open_raises_is_closed(host: BridgeHost) -> None:
    transport = BridgeTransport(host)
    transport.fail_open(HostUnreachableError("vps.example", 22, "timed out"))
    rig = Rig(transport)

    with pytest.raises(HostUnreachableError):
        rig.link.connect(PROFILE)

    assert transport.closed


def test_a_call_that_times_out_is_forgotten_and_a_late_answer_is_dropped(
    host: BridgeHost,
) -> None:
    rig, transport = _up(host)
    transport.go_silent()

    with pytest.raises(CallTimedOutError):
        rig.link.call("snapshot", timeout_s=0.05)

    assert rig.link.unanswered == 0
    transport.cut()
    assert rig.closed.wait(BOUND_S)
    assert rig.closed_with and isinstance(rig.closed_with[0], LinkLostError)
