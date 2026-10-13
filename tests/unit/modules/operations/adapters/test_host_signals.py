"""The host's word to a service manager (`EPIC-038D`): nothing by default, sd_notify by choice."""

from __future__ import annotations

import logging
import socket
from collections.abc import Iterator
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.host_signals import (
    NOTIFY_SOCKET_VARIABLE,
    WATCHDOG_USEC_VARIABLE,
    HostSignalUnavailableError,
    NullHostSignal,
    SdNotifyHostSignal,
    sd_notify_host_signal,
)


class _Manager:
    """A unix datagram socket standing in for systemd's notify socket."""

    def __init__(self, path: Path) -> None:
        self.path = str(path)
        self._socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self._socket.bind(self.path)
        self._socket.settimeout(2)

    def received(self) -> list[bytes]:
        heard: list[bytes] = []
        self._socket.settimeout(0.05)
        while True:
            try:
                heard.append(self._socket.recv(1024))
            except (TimeoutError, BlockingIOError):
                return heard

    def close(self) -> None:
        self._socket.close()


@pytest.fixture
def manager(tmp_path: Path) -> Iterator[_Manager]:
    manager = _Manager(tmp_path / "notify")
    yield manager
    manager.close()


class _Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def test_the_null_signal_says_nothing_and_asks_nothing() -> None:
    signal = NullHostSignal()

    signal.ready()
    signal.watchdog()
    signal.stopping()


def test_ready_and_stopping_reach_the_manager_as_systemd_spells_them(
    manager: _Manager,
) -> None:
    signal = SdNotifyHostSignal(manager.path, None)

    signal.ready()
    signal.stopping()

    assert manager.received() == [b"READY=1", b"STOPPING=1"]


def test_without_a_watchdog_period_no_beat_is_sent(manager: _Manager) -> None:
    signal = SdNotifyHostSignal(manager.path, None)

    signal.watchdog()

    assert manager.received() == []


def test_the_watchdog_is_beaten_at_most_once_per_half_period(manager: _Manager) -> None:
    clock = _Clock()
    signal = SdNotifyHostSignal(manager.path, 10.0, clock)

    signal.watchdog()  # the first beat goes at once
    clock.now += 9.9
    signal.watchdog()  # too soon
    clock.now += 0.1
    signal.watchdog()  # a full interval since the last

    assert manager.received() == [b"WATCHDOG=1", b"WATCHDOG=1"]


def test_a_manager_that_cannot_be_reached_is_warned_about_once_and_never_raises(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    signal = SdNotifyHostSignal(str(tmp_path / "nobody-listens"), None)

    with caplog.at_level(logging.INFO, logger="App.Operations.Host"):
        signal.ready()
        signal.stopping()

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "READY=1" in warnings[0].getMessage()


def test_an_abstract_socket_address_keeps_systemds_at_sign_convention() -> None:
    assert (
        SdNotifyHostSignal("@/org/freedesktop/x", None)._address
        == "\0/org/freedesktop/x"
    )


def test_the_adapter_is_built_from_the_environment_systemd_gives_it(
    manager: _Manager,
) -> None:
    env = {NOTIFY_SOCKET_VARIABLE: manager.path, WATCHDOG_USEC_VARIABLE: "20000000"}

    signal = sd_notify_host_signal(env, "linux")
    signal.ready()

    assert manager.received() == [b"READY=1"]


def test_it_refuses_where_it_cannot_work() -> None:
    with pytest.raises(HostSignalUnavailableError, match="Linux"):
        sd_notify_host_signal({NOTIFY_SOCKET_VARIABLE: "/run/x"}, "win32")
    with pytest.raises(HostSignalUnavailableError, match=NOTIFY_SOCKET_VARIABLE):
        sd_notify_host_signal({}, "linux")


@pytest.mark.parametrize("usec", ["", "0", "-5", "soon"])
def test_a_watchdog_period_that_is_not_a_positive_number_means_no_watchdog(
    manager: _Manager, usec: str
) -> None:
    env = {NOTIFY_SOCKET_VARIABLE: manager.path, WATCHDOG_USEC_VARIABLE: usec}

    sd_notify_host_signal(env, "linux").watchdog()

    assert manager.received() == []
