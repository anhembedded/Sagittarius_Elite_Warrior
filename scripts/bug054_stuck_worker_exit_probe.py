"""BUG-054 fault-injection probe — the real application, exited with one
background worker deliberately left running.

Run it the way the sanity tier does:

    python -m Sagittarius_Elite_Warrior.scripts.bug054_stuck_worker_exit_probe

The probe is `app_bootstrapper.main()` with exactly one line added: a task
submitted to the *real* `IThreadManager` that never returns. Every other step
— `build()`, the Qt event loop, `teardown()`, `exit_process()` — is the
production function itself, imported, not a re-implementation of it. That
distinction is the whole point: `BUG-026`/`BUG-027` were both caused by
probe scripts that grew their own copies of an interface and drifted from
it, so this one owns no application logic at all.

What it proves: before `BUG-054`'s fix the process printed `App stopped.`
and then hung forever, because `ThreadPoolExecutor`'s workers are non-daemon
and `concurrent.futures`' `atexit` hook joins them without a timeout. After
the fix the same injected fault exits with the real exit code inside the
grace period, having first logged which thread was still running.
"""

from __future__ import annotations

import sys
import threading

from PySide6.QtCore import QTimer
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

from Sagittarius_Elite_Warrior.src.presentation.ui.app_bootstrapper import (
    build,
    teardown,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.common.process_exit import (
    exit_process,
)

#: Far longer than any budget the sanity tier gives the process, so a pass
#: can only mean the exit path stopped waiting for this thread — never that
#: the thread happened to finish first.
_STUCK_SECONDS = 3600


def main() -> None:
    runtime = build()

    started = threading.Event()

    def _never_returns() -> None:
        started.set()
        threading.Event().wait(_STUCK_SECONDS)

    thread_manager = runtime.app_engine.container.resolve(IThreadManager)
    thread_manager.submit(_never_returns)
    if not started.wait(timeout=10):
        print("PROBE_ERROR: the injected task never started", file=sys.stderr)

    QTimer.singleShot(0, runtime.app.quit)
    exit_code = runtime.app.exec()
    teardown(runtime)
    exit_process(exit_code)


if __name__ == "__main__":
    main()
