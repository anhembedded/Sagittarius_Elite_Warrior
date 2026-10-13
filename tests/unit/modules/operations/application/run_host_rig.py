"""A `RunHost` on doubles, driven by hand (`EPIC-038D`): shared by the host's test files."""

from __future__ import annotations

import logging

import pytest
from Sagittarius_Elite_Warrior.src.modules.operations.application.run_host import (
    RunHost,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.run_host_parts import (
    RunHostParts,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.application.run_host_doubles import (
    HandFiredSignalSource,
    RecordingHostHealth,
    RecordingHostSignal,
    RecordingLeaver,
    RecordingStep,
    ScriptedPolicy,
)

#: Long enough that no test reaches it unless it means to: a test that waits it out is a bug.
FOREVER_S = 30.0
#: Short enough to wait out: the policy that never finishes is given up on.
BRIEF_S = 0.05


class Rig:
    def __init__(
        self,
        policy: ScriptedPolicy | None = None,
        steps: tuple[RecordingStep, ...] = (),
        stop_timeout_s: float = FOREVER_S,
        stop_grace_s: float = FOREVER_S,
    ) -> None:
        self.signals = HandFiredSignalSource()
        self.host_signal = RecordingHostSignal()
        self.health = RecordingHostHealth()
        self.policy = policy if policy is not None else ScriptedPolicy()
        self.leaver = RecordingLeaver()
        self.host = RunHost(
            RunHostParts(
                signals=self.signals,
                policy=self.policy,
                host_signal=self.host_signal,
                health=self.health,
                steps=steps,
                stop_timeout_s=stop_timeout_s,
                stop_grace_s=stop_grace_s,
                leave_process=self.leaver,
            )
        )


def transitions(caplog: pytest.LogCaptureFixture) -> list[str]:
    """The state changes, one INFO record each, in order."""
    return [
        r.getMessage()
        for r in caplog.records
        if r.getMessage().startswith("[host] ") and " -> " in r.getMessage()
    ]


def warnings_of(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
