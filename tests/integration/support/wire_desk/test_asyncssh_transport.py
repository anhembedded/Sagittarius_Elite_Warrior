"""`EPIC-047D` - the SSH adapter against a real `asyncssh` server on loopback with the real bridge behind it.

Proves what the doubles cannot: key-file login, the host key pinned through `known_hosts`, a wrong
key refused in words that name the host, the typed login errors, an abrupt cut noticed and
reconnected, and that no blocking call is inside the adapter's loop.
"""

from __future__ import annotations

import logging
import socket
import threading
from dataclasses import replace
from pathlib import Path

import asyncssh
import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.link_profile import (
    KeySource,
    LinkProtocol,
)
from Sagittarius_Elite_Warrior.src.support.wire.desk.asyncssh_transport import (
    AsyncSshTransport,
)
from Sagittarius_Elite_Warrior.src.support.wire.desk.contracts.link_errors import (
    HostUnreachableError,
    KeyFileUnusableError,
    KeyRefusedError,
    LinkLostError,
    UnknownHostKeyError,
    WrongHostKeyError,
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
from Sagittarius_Elite_Warrior.tests.integration.support.wire_desk.ssh_world import (
    Keys,
    SshHost,
    ssh_agent_holding,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.desk.desk_world import (
    DESK_HELLO,
    BridgeHost,
)

BOUND_S = 10.0


@pytest.fixture
def keys(tmp_path: Path) -> Keys:
    return Keys(tmp_path)


@pytest.fixture
def sshd(keys: Keys):
    host = SshHost(keys, BridgeHost()).start()
    keys.pin(host.port)
    yield host
    host.stop()


def _link(transport: AsyncSshTransport) -> tuple[DeskLink, threading.Event]:
    closed = threading.Event()
    link = DeskLink(
        transport,
        DESK_HELLO,
        on_event=lambda _e: None,
        on_closed=lambda _r: closed.set(),
    )
    return link, closed


def test_a_key_file_logs_in_to_the_pinned_host_and_the_bridge_answers(
    sshd: SshHost, keys: Keys
) -> None:
    link, _ = _link(AsyncSshTransport())

    link.connect(keys.profile(sshd.port))
    snapshot = link.call("snapshot")
    link.close()

    assert set(snapshot["revisions"]) == {
        b.bot_id for b in sshd.host.bots.listing().value.bots
    }  # type: ignore[attr-defined,arg-type]
    assert sshd.bridge_sessions == 1


def test_a_wrong_host_key_is_refused_with_a_sentence_that_names_the_host(
    sshd: SshHost, keys: Keys
) -> None:
    keys.pin(sshd.port, key=keys.stranger_key)
    link, _ = _link(AsyncSshTransport())

    with pytest.raises(WrongHostKeyError) as refused:
        link.connect(keys.profile(sshd.port))

    assert "127.0.0.1" in refused.value.words
    assert "pinned" in refused.value.words
    assert sshd.bridge_sessions == 0


def test_a_host_not_in_known_hosts_says_what_to_do_first(
    sshd: SshHost, keys: Keys
) -> None:
    keys.known_hosts.write_text("")
    link, _ = _link(AsyncSshTransport())

    with pytest.raises(UnknownHostKeyError) as refused:
        link.connect(keys.profile(sshd.port))

    assert "127.0.0.1" in refused.value.words
    assert "ssh -p" in refused.value.words
    assert sshd.bridge_sessions == 0


def test_a_known_hosts_file_that_does_not_exist_is_the_same_first_use_sentence(
    sshd: SshHost, keys: Keys
) -> None:
    keys.known_hosts.unlink()
    link, _ = _link(AsyncSshTransport())

    with pytest.raises(UnknownHostKeyError):
        link.connect(keys.profile(sshd.port))


def test_a_key_the_host_does_not_authorize_is_a_refused_key(
    sshd: SshHost, keys: Keys, tmp_path: Path
) -> None:
    stranger = tmp_path / "stranger"
    stranger.write_bytes(keys.stranger_key.export_private_key())
    link, _ = _link(AsyncSshTransport())

    with pytest.raises(KeyRefusedError) as refused:
        link.connect(keys.profile(sshd.port, key_file=str(stranger)))

    assert "127.0.0.1" in refused.value.words and "sew" in refused.value.words


def test_a_key_file_that_is_not_there_is_named(
    sshd: SshHost, keys: Keys, tmp_path: Path
) -> None:
    link, _ = _link(AsyncSshTransport())

    with pytest.raises(KeyFileUnusableError) as refused:
        link.connect(keys.profile(sshd.port, key_file=str(tmp_path / "nope")))

    assert "nope" in refused.value.words


def test_an_encrypted_key_is_refused_with_the_advice_to_use_the_agent(
    sshd: SshHost, keys: Keys, tmp_path: Path
) -> None:
    locked = tmp_path / "locked"
    locked.write_bytes(
        keys.client_key.export_private_key("pkcs8-pem", passphrase="secret")
    )
    link, _ = _link(AsyncSshTransport())

    with pytest.raises(KeyFileUnusableError) as refused:
        link.connect(keys.profile(sshd.port, key_file=str(locked)))

    assert "agent" in refused.value.words


def test_a_host_that_nobody_listens_on_is_unreachable_and_retriable(keys: Keys) -> None:
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        port = taken.getsockname()[1]
    link, _ = _link(AsyncSshTransport())

    with pytest.raises(HostUnreachableError) as refused:
        link.connect(keys.profile(port))

    assert refused.value.retriable
    assert str(port) in refused.value.words


def test_an_ssh_agent_logs_in_with_no_key_file_named(
    sshd: SshHost, keys: Keys, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with ssh_agent_holding(keys.client_key, tmp_path) as socket_path:
        monkeypatch.setenv("SSH_AUTH_SOCK", socket_path)
        link, _ = _link(AsyncSshTransport())

        link.connect(keys.profile(sshd.port, key_source=KeySource.AGENT, key_file=""))
        link.call("snapshot")
        link.close()

    assert sshd.bridge_sessions == 1


def test_an_agent_profile_never_passes_client_keys_none_to_asyncssh_connect(
    keys: Keys, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[dict[str, object]] = []

    async def capture(**kwargs: object) -> None:
        seen.append(kwargs)
        raise OSError("not really connecting")

    monkeypatch.setattr(asyncssh, "connect", capture)

    for profile in (
        keys.profile(22, key_source=KeySource.AGENT, key_file=""),
        keys.profile(22),
    ):
        with pytest.raises(HostUnreachableError):
            AsyncSshTransport().open(profile)

    assert len(seen) == 2
    assert all(kwargs.get("client_keys", []) is not None for kwargs in seen)
    assert all(kwargs["known_hosts"] is not None for kwargs in seen)
    assert "client_keys" not in seen[0]


def test_an_abrupt_cut_is_noticed_at_once(sshd: SshHost, keys: Keys) -> None:
    link, closed = _link(AsyncSshTransport())
    link.connect(keys.profile(sshd.port))

    sshd.cut_all()

    assert closed.wait(BOUND_S)
    with pytest.raises(LinkLostError):
        link.call("snapshot")


class _Up(ILinkObserver):
    def __init__(self) -> None:
        self.up = threading.Semaphore(0)
        self.statuses: list[LinkStatus] = []

    def on_status(self, status: LinkStatus) -> None:
        self.statuses.append(status)

    def on_link_up(self, link: DeskLink, epoch: ConnectionEpoch) -> None:
        link.call("snapshot")
        self.up.release()

    def on_event(self, epoch: ConnectionEpoch, event: dict[str, object]) -> None:
        pass


def test_the_supervisor_reconnects_over_ssh_after_a_cut_and_logs_how_long_it_took(
    sshd: SshHost, keys: Keys, caplog: pytest.LogCaptureFixture
) -> None:
    registry = TransportRegistry()
    registry.register(LinkProtocol.SSH, AsyncSshTransport)
    observer = _Up()
    supervisor = LinkSupervisor(keys.profile(sshd.port), registry, DESK_HELLO, observer)
    with caplog.at_level(logging.INFO, logger="App.LinkDesk"):
        supervisor.start()
        assert observer.up.acquire(timeout=BOUND_S)

        sshd.cut_all()

        assert observer.up.acquire(timeout=BOUND_S)
        supervisor.stop()

    assert sshd.bridge_sessions == 2
    assert observer.statuses[-1].state in (
        LinkState.CONNECTED,
        LinkState.RECONNECTING,
        LinkState.CONNECTING,
    )
    took = [
        r.getMessage() for r in caplog.records if "[link-reconnect]" in r.getMessage()
    ]
    assert len(took) == 1
    milliseconds = int(took[0].split("welcomed again ")[1].split(" ms")[0])
    assert (
        milliseconds < 2000
    )  # the loopback figure; the real link's 2 s is the owner's measurement


def test_no_call_inside_the_adapters_loop_blocks_it(
    sshd: SshHost, keys: Keys, caplog: pytest.LogCaptureFixture
) -> None:
    """asyncio's debug mode reports any callback that holds the loop over `slow_callback_duration`."""
    transport = AsyncSshTransport(loop_debug=True)
    link, _ = _link(transport)
    with caplog.at_level(logging.WARNING, logger="asyncio"):
        link.connect(keys.profile(sshd.port))
        for _ in range(20):
            link.call("snapshot")
        link.close()

    slow = [
        r.getMessage()
        for r in caplog.records
        if r.name == "asyncio" and "took" in r.getMessage()
    ]
    assert slow == []


def test_the_loop_runs_on_a_thread_of_its_own(sshd: SshHost, keys: Keys) -> None:
    before = set(threading.enumerate())
    link, _ = _link(AsyncSshTransport())
    link.connect(keys.profile(sshd.port))

    loops = [
        t for t in set(threading.enumerate()) - before if t.name == "link-ssh-loop"
    ]
    assert len(loops) == 1 and loops[0] is not threading.current_thread()
    link.close()

    assert not loops[0].is_alive()


def test_a_profile_is_a_value_the_tests_rebuild_with_replace(keys: Keys) -> None:
    profile = keys.profile(22)

    assert replace(profile, port=23).port == 23 and profile.port == 22
