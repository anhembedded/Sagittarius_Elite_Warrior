"""Doubles for the `run` host's collaborators, each derived from its port (`EPIC-038D`)."""

from __future__ import annotations

import threading
from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_state import (
    HostState,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_host_health import (
    IHostHealth,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_host_signal import (
    IHostSignal,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_host_step import (
    IHostStep,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_shutdown_policy import (
    IShutdownPolicy,
    StopLedger,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_shutdown_signal_source import (
    IShutdownSignalSource,
)


class HandFiredSignalSource(IShutdownSignalSource):
    """A source the test fires by hand, as an operator presses a key."""

    def __init__(self) -> None:
        self.installed = False
        self.restored = 0
        self._on_signal: Callable[[], None] | None = None

    def install(self, on_signal: Callable[[], None]) -> None:
        self.installed = True
        self._on_signal = on_signal

    def restore(self) -> None:
        self.installed = False
        self.restored += 1

    def fire(self) -> None:
        assert self._on_signal is not None, "the host installed no handler"
        self._on_signal()


class RecordingHostSignal(IHostSignal):
    def __init__(self) -> None:
        self.calls: list[str] = []

    def ready(self) -> None:
        self.calls.append("ready")

    def watchdog(self) -> None:
        self.calls.append("watchdog")

    def stopping(self) -> None:
        self.calls.append("stopping")


class RecordingHostHealth(IHostHealth):
    def __init__(self) -> None:
        self.states: list[HostState] = []
        self.published: list[HostState] = []

    def set_state(self, state: HostState) -> None:
        self.states.append(state)

    def publish_now(self) -> None:
        self.published.append(self.states[-1])


class RecordingStep(IHostStep):
    def __init__(self, name: str, log: list[str], fails: bool = False) -> None:
        self.name = name
        self._log = log
        self._fails = fails

    def run(self) -> None:
        self._log.append(self.name)
        if self._fails:
            raise RuntimeError(f"{self.name} failed")


class ScriptedPolicy(IShutdownPolicy):
    """Does what the test scripts: finish at once, never finish, or fail.

    `leaves` are the bots it begins and does not finish, so a test can say what
    the host must report when it gives up."""

    name = "scripted"

    def __init__(
        self,
        *,
        leaves: tuple[str, ...] = (),
        blocks: bool = False,
        fails: bool = False,
        during: Callable[[], None] | None = None,
    ) -> None:
        self._leaves = leaves
        self._blocks = blocks
        self._fails = fails
        self._during = during
        self.applied = 0
        self.gave_up = threading.Event()

    def apply(self, ledger: StopLedger, give_up: threading.Event) -> None:
        self.applied += 1
        for bot_id in self._leaves:
            ledger.begin(bot_id, "STOPPING", 3)
        if self._during is not None:
            self._during()
        if self._fails:
            raise RuntimeError("the exchange said no")
        if self._blocks:
            assert give_up.wait(10), "the host never told the policy to give up"
            self.gave_up.set()
