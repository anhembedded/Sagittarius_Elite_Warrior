"""`EPIC-047D` - the supervisor keeps a profile's link up: a cut is reconnected at once with a fresh epoch, a refusal is not retried."""

from __future__ import annotations

import threading
from dataclasses import replace

from Sagittarius_Elite_Warrior.src.core.contracts.link_profile import (
    LinkProtocol,
    ReconnectPolicy,
)
from Sagittarius_Elite_Warrior.src.support.wire.desk.contracts.link_errors import (
    HostUnreachableError,
    KeyRefusedError,
    LinkError,
    VersionDifferenceError,
)
from Sagittarius_Elite_Warrior.src.support.wire.desk.contracts.link_status import (
    LinkState,
    LinkStatus,
)
from Sagittarius_Elite_Warrior.src.support.wire.desk.desk_link import DeskLink
from Sagittarius_Elite_Warrior.src.support.wire.desk.link_supervisor import (
    ConnectionEpoch,
    ILinkObserver,
    LinkSupervisor,
)
from Sagittarius_Elite_Warrior.src.support.wire.desk.transport_registry import (
    TransportRegistry,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.desk.desk_world import (
    DESK_HELLO,
    PROFILE,
    BridgeHost,
    BridgeTransport,
)

BOUND_S = 5.0
QUICK = replace(PROFILE, reconnect=ReconnectPolicy(first_delay_s=0.0, max_delay_s=0.0))


class Watcher(ILinkObserver):
    def __init__(self) -> None:
        self.statuses: list[LinkStatus] = []
        self.epochs: list[ConnectionEpoch] = []
        self.snapshots: list[dict[str, object]] = []
        self.up = threading.Semaphore(0)
        self.finished = threading.Event()

    def on_status(self, status: LinkStatus) -> None:
        self.statuses.append(status)
        if status.state is LinkState.FAILED:
            self.finished.set()

    def on_link_up(self, link: DeskLink, epoch: ConnectionEpoch) -> None:
        self.epochs.append(epoch)
        self.snapshots.append(link.call("snapshot"))
        link.call("subscribe")
        self.up.release()

    def on_event(self, epoch: ConnectionEpoch, event: dict[str, object]) -> None:
        pass


class Transports:
    """Hands out one scripted transport per attempt; `made` keeps them."""

    def __init__(self, host: BridgeHost, *script: LinkError | None) -> None:
        self.host = host
        self.script = list(script)
        self.made: list[BridgeTransport] = []

    def registry(self) -> TransportRegistry:
        registry = TransportRegistry()
        registry.register(LinkProtocol.SSH, self._next)
        return registry

    def _next(self) -> BridgeTransport:
        transport = BridgeTransport(self.host)
        failure = self.script.pop(0) if self.script else None
        if failure is not None:
            transport.fail_open(failure)
        self.made.append(transport)
        return transport


def _supervise(transports: Transports, profile=QUICK) -> tuple[LinkSupervisor, Watcher]:
    watcher = Watcher()
    supervisor = LinkSupervisor(profile, transports.registry(), DESK_HELLO, watcher)
    supervisor.start()
    return supervisor, watcher


def test_a_profile_connects_and_the_observer_takes_the_first_snapshot() -> None:
    transports = Transports(BridgeHost())
    supervisor, watcher = _supervise(transports)

    assert watcher.up.acquire(timeout=BOUND_S)

    assert supervisor.status.state is LinkState.CONNECTED
    assert set(watcher.snapshots[0]) >= {"seq", "list", "revisions", "facts"}
    supervisor.stop()


def test_an_abrupt_cut_is_reconnected_at_once_on_a_new_transport_and_a_fresh_gate() -> (
    None
):
    transports = Transports(BridgeHost())
    supervisor, watcher = _supervise(transports)
    assert watcher.up.acquire(timeout=BOUND_S)
    first = watcher.epochs[0]
    first.gate.offer("b-0001", 1, object())

    transports.made[0].cut()

    assert watcher.up.acquire(timeout=BOUND_S)
    second = watcher.epochs[1]
    assert second.number == first.number + 1
    assert second.gate is not first.gate
    assert second.gate.revision_of("b-0001") is None
    assert len(transports.made) == 2 and transports.made[1] is not transports.made[0]
    states = [s.state for s in watcher.statuses]
    assert LinkState.RECONNECTING in states
    assert states[-1] is LinkState.CONNECTED
    supervisor.stop()


def test_while_reconnecting_the_tab_is_told_it_is_disconnected_and_when_its_data_is_from() -> (
    None
):
    transports = Transports(
        BridgeHost(), None, HostUnreachableError("vps.example", 22, "down")
    )
    supervisor, watcher = _supervise(
        transports, replace(QUICK, reconnect=ReconnectPolicy(max_attempts=3))
    )
    assert watcher.up.acquire(timeout=BOUND_S)

    transports.made[0].cut()
    assert watcher.up.acquire(timeout=BOUND_S)

    reconnecting = [s for s in watcher.statuses if s.state is LinkState.RECONNECTING]
    assert reconnecting
    assert any("disconnected, data as of" in s.words for s in reconnecting)
    assert all(s.data_as_of is not None for s in reconnecting)
    supervisor.stop()


def test_an_unreachable_host_is_retried_until_it_answers() -> None:
    down = HostUnreachableError("vps.example", 22, "timed out")
    transports = Transports(BridgeHost(), down, down)
    supervisor, watcher = _supervise(transports)

    assert watcher.up.acquire(timeout=BOUND_S)

    assert len(transports.made) == 3
    assert supervisor.status.state is LinkState.CONNECTED
    supervisor.stop()


def test_a_policy_with_a_limit_gives_up_with_the_last_reason() -> None:
    down = HostUnreachableError("vps.example", 22, "timed out")
    transports = Transports(BridgeHost(), down, down, down, down)
    supervisor, watcher = _supervise(
        transports,
        replace(
            QUICK,
            reconnect=ReconnectPolicy(
                first_delay_s=0.0, max_delay_s=0.0, max_attempts=2
            ),
        ),
    )

    assert watcher.finished.wait(BOUND_S)

    assert supervisor.status.state is LinkState.FAILED
    assert "vps.example" in supervisor.status.words
    assert len(transports.made) == 3  # the first try, then the two the policy allows


def test_a_refused_key_is_not_retried() -> None:
    transports = Transports(BridgeHost(), KeyRefusedError("vps.example", "sew"), None)
    supervisor, watcher = _supervise(transports)

    assert watcher.finished.wait(BOUND_S)
    assert supervisor.join(BOUND_S)

    assert len(transports.made) == 1
    assert "refused the key" in supervisor.status.words


def test_a_version_difference_is_not_retried() -> None:
    transports = Transports(
        BridgeHost(), VersionDifferenceError("the host runs build 1"), None
    )
    supervisor, watcher = _supervise(transports)

    assert watcher.finished.wait(BOUND_S)
    assert supervisor.join(BOUND_S)

    assert len(transports.made) == 1


def test_a_missing_transport_for_the_protocol_ends_with_the_sentence() -> None:
    watcher = Watcher()
    supervisor = LinkSupervisor(QUICK, TransportRegistry(), DESK_HELLO, watcher)
    supervisor.start()

    assert watcher.finished.wait(BOUND_S)
    assert "no transport" in supervisor.status.words


def test_stop_ends_a_connected_supervisor_and_closes_its_link() -> None:
    transports = Transports(BridgeHost())
    supervisor, watcher = _supervise(transports)
    assert watcher.up.acquire(timeout=BOUND_S)

    supervisor.stop()

    assert supervisor.join(BOUND_S)
    assert transports.made[0].closed
    assert len(transports.made) == 1


def test_the_time_from_the_cut_to_the_next_welcome_is_logged(caplog) -> None:
    transports = Transports(BridgeHost())
    with caplog.at_level("INFO", logger="App.LinkDesk"):
        supervisor, watcher = _supervise(transports)
        assert watcher.up.acquire(timeout=BOUND_S)
        transports.made[0].cut()
        assert watcher.up.acquire(timeout=BOUND_S)
        supervisor.stop()

    lines = [
        r.getMessage() for r in caplog.records if "[link-reconnect]" in r.getMessage()
    ]
    assert len(lines) == 1 and " ms after the cut" in lines[0]
