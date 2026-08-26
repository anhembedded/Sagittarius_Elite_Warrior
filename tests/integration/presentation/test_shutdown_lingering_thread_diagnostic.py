"""`BUG-052` — the app must name whatever is holding the process open.

@details The reported session shut down cleanly, logged `App stopped.`, and
then never returned, emitting nothing further. Only a non-daemon thread can do
that: CPython joins them after `main()` returns — for `ThreadPoolExecutor`
workers via the `_python_exit` hook `concurrent.futures.thread` registers,
which joins **regardless** of the `wait=False` the engine passes to
`shutdown()` (the mechanism `BUG-041` established). That join happens after
logging has stopped, so the hang is silent by construction.

These run out of process on purpose. `tests/sanity/test_composition_root.py`
already notes why: `threading.enumerate()` inside pytest is only a proxy for a
process actually dying, and this bug is precisely about the moment *after*
everything an in-process test can observe.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_PROBE = "Sagittarius_Elite_Warrior.scripts.bug052_shutdown_thread_probe"

#: The probe's stuck task sleeps 20s; the process cannot exit before then, so
#: this must clear that plus boot and teardown.
_HUNG_RUN_TIMEOUT_SECONDS = 90

#: A clean run has nothing to wait for.
_CLEAN_RUN_TIMEOUT_SECONDS = 60

_BLOCKING_VERDICT = "NON-DAEMON thread(s) hold the process open"
_CLEAN_VERDICT = "no non-daemon survivor"
_DIAGNOSTIC_LOG = "the process will not exit until they finish (BUG-052)"


def _run(args: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    workspace_root = Path(__file__).resolve().parents[4]
    return subprocess.run(
        [sys.executable, "-m", _PROBE, *args],
        cwd=workspace_root,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def test_a_normal_shutdown_leaves_nothing_that_could_block_exit() -> None:
    """The baseline that makes the failing case meaningful: booting and
    tearing down the real app leaves no non-daemon thread at all, so a
    survivor in the other test is caused by the task, not by the app's own
    shutdown being generally leaky."""
    result = _run([], _CLEAN_RUN_TIMEOUT_SECONDS)
    output = result.stdout + result.stderr

    assert result.returncode == 0, output
    assert _CLEAN_VERDICT in result.stdout, output


def test_a_task_outliving_shutdown_is_named_rather_than_hanging_silently() -> None:
    """The regression this bug is really about.

    Not "the process exits promptly" — it cannot, and forcing it to would risk
    truncating a real database write; per-task cancellation is where a fix
    belongs (`BUG-041`'s approach). What must never happen again is the app
    going *silent*: the next occurrence has to name the thread and print where
    it is stuck, in one run, instead of costing another blind session.
    """
    result = _run(["--stuck-task"], _HUNG_RUN_TIMEOUT_SECONDS)
    output = result.stdout + result.stderr

    assert result.returncode == 1, output
    assert _BLOCKING_VERDICT in result.stdout, output
    # The app's own diagnostic, not just the probe's: this is the line a user
    # would be able to attach to a bug report.
    assert _DIAGNOSTIC_LOG in output, output
    assert "ThreadPoolExecutor" in output, output
