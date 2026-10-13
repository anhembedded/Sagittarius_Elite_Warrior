"""What the host tells a service manager (`EPIC-038D`): nothing, or systemd's sd_notify.

`NullHostSignal` is the default. `SdNotifyHostSignal` (`--host-signal sdnotify`) speaks
the sd_notify protocol for a `Type=notify` unit: `READY=1` when the host serves,
`WATCHDOG=1` at half the unit's `WatchdogSec` while it lives, `STOPPING=1` when it
drains. It is Linux-only and **does not work inside a container** whose `NOTIFY_SOCKET`
is not mounted into it; the unit file of `EPIC-038H` says when to use it.

Every method is best effort: a manager that cannot be reached must never stop the host,
so a failed send is logged once at WARNING and the host carries on.
"""

from __future__ import annotations

import logging
import os
import socket
import sys
import time
from collections.abc import Callable, Mapping

from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_host_signal import (
    IHostSignal,
)

logger = logging.getLogger("App.Operations.Host")

NOTIFY_SOCKET_VARIABLE = "NOTIFY_SOCKET"
WATCHDOG_USEC_VARIABLE = "WATCHDOG_USEC"
_MICROSECONDS = 1_000_000


class HostSignalUnavailableError(RuntimeError):
    """`--host-signal sdnotify` was asked for where it cannot work."""


class NullHostSignal(IHostSignal):
    def ready(self) -> None:
        return None

    def watchdog(self) -> None:
        return None

    def stopping(self) -> None:
        return None


class SdNotifyHostSignal(IHostSignal):
    def __init__(
        self,
        notify_socket: str,
        watchdog_interval_s: float | None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._address = _address(notify_socket)
        self._watchdog_interval_s = watchdog_interval_s
        self._monotonic = monotonic
        self._last_beat: float | None = None
        self._warned = False

    def ready(self) -> None:
        self._send(b"READY=1")

    def stopping(self) -> None:
        self._send(b"STOPPING=1")

    def watchdog(self) -> None:
        """Passes a beat on at most every half interval; the host calls this every quarter second."""
        if self._watchdog_interval_s is None:
            return
        now = self._monotonic()
        if (
            self._last_beat is not None
            and now - self._last_beat < self._watchdog_interval_s
        ):
            return
        self._last_beat = now
        self._send(b"WATCHDOG=1")

    def _send(self, message: bytes) -> None:
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as client:
                client.sendto(message, self._address)
        except OSError as failure:
            if not self._warned:
                self._warned = True
                logger.warning(
                    "[host-signal] the service manager could not be told %s (%s); "
                    "not reported again",
                    message.decode("ascii"),
                    failure,
                )


def _address(notify_socket: str) -> str:
    """A leading `@` names a socket in the abstract namespace (systemd's convention)."""
    return "\0" + notify_socket[1:] if notify_socket.startswith("@") else notify_socket


def sd_notify_host_signal(
    environment: Mapping[str, str] | None = None, platform: str = sys.platform
) -> SdNotifyHostSignal:
    """The adapter for this process, or why it cannot be had.

    @raise HostSignalUnavailableError not Linux, or systemd gave this process no
    `NOTIFY_SOCKET` (the unit is not `Type=notify`, or this is a container without it).
    """
    env = os.environ if environment is None else environment
    if not platform.startswith("linux"):
        raise HostSignalUnavailableError(
            f"--host-signal sdnotify works on Linux only, not {platform}"
        )
    notify_socket = env.get(NOTIFY_SOCKET_VARIABLE)
    if not notify_socket:
        raise HostSignalUnavailableError(
            f"--host-signal sdnotify needs {NOTIFY_SOCKET_VARIABLE}, which systemd sets "
            "for a Type=notify unit; this process has none (a container without the "
            "socket mounted does not either)"
        )
    return SdNotifyHostSignal(notify_socket, _watchdog_interval_s(env))


def _watchdog_interval_s(env: Mapping[str, str]) -> float | None:
    """Half the unit's watchdog period, or `None` when the unit sets none."""
    raw = env.get(WATCHDOG_USEC_VARIABLE, "")
    if not raw.isdecimal() or int(raw) <= 0:
        return None
    return int(raw) / _MICROSECONDS / 2
