"""`BUG-054` regression at the only tier that can prove it — a real process.

The reported failure left no trace an in-process test can observe: every
line of application code ran, `App stopped.` was logged, and only then did
the process refuse to return. The cause lives in CPython's exit sequence,
not in the app's: `ThreadPoolExecutor` workers are non-daemon, both pools
are shut down with `wait=False` so a slow task cannot stall shutdown, and
`concurrent.futures`' `atexit` hook then joins every worker with no timeout.

So this test does what `test_self_check_process.py` does for the clean case,
with the fault injected: it runs `scripts/bug054_stuck_worker_exit_probe.py`
— the real `build()`/`teardown()`/`exit_process()` with one task that never
returns — and asserts the process still dies. Measured before the fix: the
same probe printed `App stopped.` and then hung indefinitely, surviving
`SIGTERM` (the app's own handler calls `app.quit()`, which does nothing once
the event loop is already gone) and needing `SIGKILL`.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

#: Real boot + teardown (~4s) plus `exit_process`'s own 5s grace period,
#: with headroom for a loaded CI runner. The budget asserts "the process
#: terminates at all"; a hang fails here as `TimeoutExpired`, a real test
#: failure, instead of a hung CI job.
_PROCESS_BUDGET_SECONDS = 45

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _run_probe() -> tuple[subprocess.CompletedProcess[str], float]:
    started = time.monotonic()
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "Sagittarius_Elite_Warrior.scripts.bug054_stuck_worker_exit_probe",
        ],
        cwd=str(_REPO_ROOT.parent),
        capture_output=True,
        text=True,
        timeout=_PROCESS_BUDGET_SECONDS,
        check=False,
    )
    return result, time.monotonic() - started


def test_the_process_exits_even_with_a_worker_that_never_finishes() -> None:
    result, elapsed = _run_probe()

    assert result.returncode == 0, (
        f"the probe exited {result.returncode} after {elapsed:.1f}s.\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
    combined = result.stdout + result.stderr
    assert "App stopped." in combined, (
        "the probe must reach the same point the bug report's log reached — "
        f"a full, clean Engine shutdown:\n{combined}"
    )
    assert "[process-exit]" in combined, (
        "the exit path must report that it had to stop waiting; an exit with "
        "no such line means the fix never ran and the process happened to be "
        f"lucky:\n{combined}"
    )
    assert "ThreadPoolExecutor" in combined, (
        "the forced-exit warning must name the surviving worker thread — "
        "naming it is the half of this fix that makes the NEXT occurrence "
        f"diagnosable:\n{combined}"
    )
