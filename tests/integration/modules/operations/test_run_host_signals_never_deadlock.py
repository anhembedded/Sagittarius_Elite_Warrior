"""`EPIC-038D` review: a signal that lands while the host waits must never hang it.

A Python signal handler runs on the main thread between two bytecodes - including
inside `threading.Event.wait`, while that call holds the event's non-re-entrant lock.
A handler that calls `Event.set()` then blocks on the lock its own thread holds, and
the host never drains: no `app.stop()`, no STOPPED snapshot, only the supervisor's
SIGKILL ends it. The window is microseconds per wake, so one real `SIGTERM` almost
never finds it; this sends hundreds, from a thread, at a host whose wait does nothing
but wait, in a child process that a hang cannot take the test run down with.

Retire when: `RunHost` waits on something no signal handler can lock, and this has
been green for a release (it is cheap, so there is no reason to retire it earlier).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_REPO_PARENT = Path(__file__).resolve().parents[5]
_BUDGET_SECONDS = 40
_DUMP_AFTER_SECONDS = 25
_ROUNDS = 400

pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="sends POSIX signals to itself; the Windows adapter is covered with its own numbers",
)

_CHILD = f"""
import faulthandler, os, random, signal, threading
faulthandler.dump_traceback_later({_DUMP_AFTER_SECONDS}, exit=False)  # a hang names its own stack
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.signal_sources import PosixSignalSource
from Sagittarius_Elite_Warrior.src.modules.operations.application import run_host
from Sagittarius_Elite_Warrior.src.modules.operations.application.run_host import RunHost
from Sagittarius_Elite_Warrior.src.modules.operations.application.run_host_parts import RunHostParts
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.application.run_host_doubles import (
    RecordingHostHealth, RecordingHostSignal, ScriptedPolicy,
)

run_host.WAIT_STEP_SECONDS = 0  # the wait does nothing but wait: the widest window there is
random.seed(7)


class WaitingHostSignal(RecordingHostSignal):
    # watchdog() runs each time the wait comes back empty: the host is waiting now.

    def __init__(self):
        super().__init__()
        self.waiting = []

    def watchdog(self):
        self.waiting.append(1)


def sender(pid, waiting):
    while not waiting:  # the signal must land while the main thread is inside the wait
        pass
    for _ in range(random.randint(0, 400)):
        pass
    os.kill(pid, signal.SIGTERM)


for round_number in range({_ROUNDS}):
    source = PosixSignalSource()
    host_signal = WaitingHostSignal()
    host = RunHost(RunHostParts(
        signals=source,
        policy=ScriptedPolicy(),
        host_signal=host_signal,
        health=RecordingHostHealth(),
        steps=(),
        stop_timeout_s=30.0,
    ))
    host.listen()
    host.begin()
    threading.Thread(target=sender, args=(os.getpid(), host_signal.waiting), daemon=True).start()
    assert host.wait_for_stop() is True
    host.release()
print("SIGNALS_SURVIVED", {_ROUNDS}, flush=True)
"""


def test_hundreds_of_signals_landing_in_the_wait_never_hang_the_host() -> None:
    try:
        done = subprocess.run(
            [sys.executable, "-X", "faulthandler", "-c", _CHILD],
            cwd=str(_REPO_PARENT),
            capture_output=True,
            text=True,
            timeout=_BUDGET_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as hung:
        pytest.fail(
            f"the host hung inside its wait after a signal (killed after {_BUDGET_SECONDS} s)\n"
            f"{(hung.stderr.decode() if isinstance(hung.stderr, bytes) else hung.stderr or '')[-2500:]}"
        )

    assert done.returncode == 0, done.stdout + done.stderr
    assert f"SIGNALS_SURVIVED {_ROUNDS}" in done.stdout
