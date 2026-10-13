"""What a `RunHost` is made of (`EPIC-038D`).

One frozen object instead of eight keyword arguments: the entry point builds it,
a test builds it with doubles, and a new collaborator is one field here.
"""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass

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
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_shutdown_signal_source import (
    IShutdownSignalSource,
)

#: What the rest of a stop may take after the policy's `--stop-timeout`: the probes run at
#: DRAINING, the module shutdowns and each bot worker's close (up to 10 s apiece). The whole
#: stop is bound by `stop_timeout_s + STOP_GRACE_SECONDS`, which is what a service unit's
#: `TimeoutStopSec` must exceed (`SPEC-015`, `EPIC-038H`).
STOP_GRACE_SECONDS = 30.0
#: How long the forced exit waits for the STOPPED snapshot to be written. The snapshot is
#: best effort: the probes that run before it can sit on a dead exchange, and the exit must not.
LEAVE_PUBLISH_SECONDS = 2.0


def leave_the_process(status: int) -> None:
    """End the process now, without unwinding: the stop has run out of time or of patience.

    `os._exit` skips every `finally` and `atexit` on purpose - the workers it would
    wait for are the reason the host is leaving - so what the log and the streams hold
    is flushed first. The lock is released by the operating system with the process.
    """
    logging.shutdown()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(status)


@dataclass(frozen=True, slots=True)
class RunHostParts:
    signals: IShutdownSignalSource
    policy: IShutdownPolicy
    host_signal: IHostSignal
    health: IHostHealth
    steps: tuple[IHostStep, ...]
    stop_timeout_s: float
    stop_grace_s: float = STOP_GRACE_SECONDS
    leave_publish_s: float = LEAVE_PUBLISH_SECONDS
    leave_process: Callable[[int], None] = leave_the_process
