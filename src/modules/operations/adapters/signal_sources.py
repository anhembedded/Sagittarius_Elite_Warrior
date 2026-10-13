"""Real shutdown signals, per platform (`EPIC-038D`).

A service manager asks a process to stop with a signal: SIGTERM on POSIX (and
SIGINT from a terminal's Ctrl-C), Ctrl-C / Ctrl-Break on a Windows console
(`SIGINT` and `SIGBREAK`; a service wrapper such as NSSM sends Ctrl-C first,
`RESEARCH` R10). The two adapters differ only in the names they listen for, so
both are one class over a list of names; `signal` itself is a parameter so a test
can see what was installed without sending anything to the test runner.

`signal.signal` works only on the main thread, and `RunHost.begin()` runs there
(the Engine starts hosted services from `app.boot()`, on the caller's thread).
"""

from __future__ import annotations

import logging
import signal
import sys
from collections.abc import Callable
from types import FrameType
from typing import Any, Protocol

from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_shutdown_signal_source import (
    IShutdownSignalSource,
)

logger = logging.getLogger("App.Operations.Signals")

type Handler = Callable[[int, FrameType | None], Any] | int | signal.Handlers | None


class SignalApi(Protocol):
    """The part of the `signal` module this source uses."""

    def signal(self, signalnum: int, handler: Handler, /) -> Handler: ...


class _StdlibSignalApi:
    """The real `signal` module behind the `SignalApi` protocol."""

    def signal(self, signalnum: int, handler: Handler, /) -> Handler:
        return signal.signal(signalnum, handler)  # type: ignore[arg-type]


def _platform_number(name: str) -> int | None:
    """The signal number the running platform gives `name`, or `None` if it has none."""
    number = getattr(signal, name, None)
    return None if number is None else int(number)


class NamedSignalSource(IShutdownSignalSource):
    """Calls `on_signal` when the process receives any of `names`.

    `number_of` says which number a name has on this platform; a test passes the
    numbers of another platform to see what that platform's adapter would install.
    """

    def __init__(
        self,
        names: tuple[str, ...],
        api: SignalApi | None = None,
        number_of: Callable[[str], int | None] = _platform_number,
    ) -> None:
        self._names = names
        self._api = api if api is not None else _StdlibSignalApi()
        self._number_of = number_of
        self._previous: dict[int, Handler] = {}

    def install(self, on_signal: Callable[[], None]) -> None:
        def handle(_number: int, _frame: FrameType | None) -> None:
            on_signal()

        heard: list[str] = []
        for name in self._names:
            number = self._number_of(name)
            if number is None:
                logger.warning(
                    "[signals] %s does not exist on this platform; not listening for it",
                    name,
                )
                continue
            self._previous[number] = self._api.signal(number, handle)
            heard.append(name)
        logger.info("[signals] a request to stop is one of: %s", ", ".join(heard))

    def restore(self) -> None:
        for number, previous in self._previous.items():
            self._api.signal(number, previous)
        self._previous.clear()


class PosixSignalSource(NamedSignalSource):
    """SIGTERM (a service manager's stop) and SIGINT (a terminal's Ctrl-C)."""

    def __init__(
        self,
        api: SignalApi | None = None,
        number_of: Callable[[str], int | None] = _platform_number,
    ) -> None:
        super().__init__(("SIGTERM", "SIGINT"), api, number_of)


class WindowsSignalSource(NamedSignalSource):
    """SIGINT (Ctrl-C) and SIGBREAK (Ctrl-Break, a service wrapper's second ask)."""

    def __init__(
        self,
        api: SignalApi | None = None,
        number_of: Callable[[str], int | None] = _platform_number,
    ) -> None:
        super().__init__(("SIGINT", "SIGBREAK"), api, number_of)


def default_shutdown_signal_source(
    platform: str = sys.platform,
) -> IShutdownSignalSource:
    """The source for this platform."""
    return WindowsSignalSource() if platform == "win32" else PosixSignalSource()
