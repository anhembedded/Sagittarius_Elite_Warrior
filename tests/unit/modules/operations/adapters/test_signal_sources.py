"""The shutdown signal adapters install the right handlers and give them back (`EPIC-038D`).

The signal API is a double derived from `SignalApi`; nothing here is sent to the
test runner. The real signal, in a real process, is `test_run_process.py`.
"""

from __future__ import annotations

import signal
import sys

from Sagittarius_Elite_Warrior.src.modules.operations.adapters.signal_sources import (
    Handler,
    NamedSignalSource,
    PosixSignalSource,
    WindowsSignalSource,
    default_shutdown_signal_source,
)


class _RecordingSignalApi:
    """Keeps a handler per signal number, as the process does."""

    def __init__(self, held: dict[int, Handler] | None = None) -> None:
        self.handlers: dict[int, Handler] = dict(held or {})

    def signal(self, signalnum: int, handler: Handler, /) -> Handler:
        previous = self.handlers.get(signalnum, signal.SIG_DFL)
        self.handlers[signalnum] = handler
        return previous

    def deliver(self, signalnum: int) -> None:
        handler = self.handlers[signalnum]
        assert callable(handler), f"signal {signalnum} has no Python handler"
        handler(signalnum, None)


def test_a_posix_source_listens_for_sigterm_and_sigint() -> None:
    api = _RecordingSignalApi()
    heard: list[str] = []

    PosixSignalSource(api).install(lambda: heard.append("stop"))
    api.deliver(signal.SIGTERM)
    api.deliver(signal.SIGINT)

    assert heard == ["stop", "stop"]
    assert set(api.handlers) == {signal.SIGTERM, signal.SIGINT}


#: Windows' numbers for the two names its console sends (`signal.h`); the adapter is
#: given them so this test runs, and proves the same thing, on any platform.
_WINDOWS_NUMBERS = {"SIGINT": 2, "SIGBREAK": 21}


def test_a_windows_source_listens_for_ctrl_c_and_ctrl_break() -> None:
    api = _RecordingSignalApi()
    heard: list[str] = []

    WindowsSignalSource(api, _WINDOWS_NUMBERS.get).install(lambda: heard.append("stop"))
    api.deliver(_WINDOWS_NUMBERS["SIGINT"])
    api.deliver(_WINDOWS_NUMBERS["SIGBREAK"])

    assert heard == ["stop", "stop"]
    assert set(api.handlers) == set(_WINDOWS_NUMBERS.values())


def test_a_name_the_platform_lacks_is_skipped_not_fatal() -> None:
    api = _RecordingSignalApi()

    NamedSignalSource(("SIGINT", "SIGNOSUCHTHING"), api).install(lambda: None)

    assert set(api.handlers) == {signal.SIGINT}


def test_restore_gives_back_exactly_what_was_there() -> None:
    before = signal.SIG_IGN
    api = _RecordingSignalApi({signal.SIGTERM: before})
    source = PosixSignalSource(api)
    source.install(lambda: None)

    source.restore()
    source.restore()  # harmless twice

    assert api.handlers[signal.SIGTERM] == before
    assert api.handlers[signal.SIGINT] == signal.SIG_DFL


def test_the_platform_picks_its_source() -> None:
    assert isinstance(default_shutdown_signal_source("win32"), WindowsSignalSource)
    assert isinstance(default_shutdown_signal_source("linux"), PosixSignalSource)
    assert isinstance(default_shutdown_signal_source(sys.platform), NamedSignalSource)
