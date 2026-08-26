"""`BUG-052` — who is still holding the process open after `App stopped.`?

@details The bug report's own step 1: the session log ends *at* `App stopped.`,
which is exactly one line before the interesting moment, so the log cannot say
what kept the interpreter alive. This probe runs the real production
`build()`/`teardown()` pair and then dumps every surviving thread with its
daemon flag and its current stack — the evidence the log cannot give.

Only **non-daemon** threads keep CPython from exiting: the interpreter joins
them after `main()` returns and blocks for as long as they run. Daemon threads
are killed outright, so a daemon survivor is noise here, not a suspect. The
probe reports both, but only fails on non-daemon survivors.

Run it in each mode and compare — the reported session had run a Historical
Tick Backtest before closing, so a difference between the two modes is itself
the finding:

    python -m Sagittarius_Elite_Warrior.scripts.bug052_shutdown_thread_probe
    python -m Sagittarius_Elite_Warrior.scripts.bug052_shutdown_thread_probe --backtest

Exit code 0 means every non-daemon thread was gone; 1 means at least one was
still running, and its stack is printed above the verdict.
"""

from __future__ import annotations

import os
import sys
import threading
import time
import traceback

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer

from Sagittarius_Elite_Warrior.src.presentation.ui.app_bootstrapper import (
    build,
    teardown,
)

_STUCK_FLAG = "--stuck-task"

#: How long to let a straggler finish before calling it a survivor. Teardown is
#: synchronous, so anything still running well after it returns is not "just
#: about to finish" — the reported hang lasted indefinitely.
_GRACE_SECONDS = 2.0

#: Long enough that a hang is unmistakable next to teardown's own duration,
#: short enough that the probe still terminates on its own.
_STUCK_TASK_SECONDS = 20.0


def _describe(thread: threading.Thread) -> str:
    frame = sys._current_frames().get(thread.ident or -1)
    where = (
        "".join(traceback.format_stack(frame))
        if frame is not None
        else "  <no frame>\n"
    )
    kind = "daemon" if thread.daemon else "NON-DAEMON"
    return f"--- {thread.name} [{kind}] alive={thread.is_alive()}\n{where}"


def main() -> int:
    runtime = build()

    if _STUCK_FLAG in sys.argv:
        # A task that outlives shutdown, standing in for whatever the reported
        # session still had running. It checks no cancellation token -- which
        # is the point: ThreadManagerModule.shutdown() passes wait=False
        # precisely so it does not block, leaving the interpreter to join the
        # worker later, after all logging has stopped.
        from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

        thread_manager = runtime.app_engine.context.container.resolve(IThreadManager)
        thread_manager.submit(time.sleep, _STUCK_TASK_SECONDS)
        print(
            f"[probe] submitted a {_STUCK_TASK_SECONDS}s task that ignores cancellation"
        )

    QTimer.singleShot(0, runtime.app.quit)
    runtime.app.exec()

    teardown(runtime)
    print("[probe] teardown() returned — this is where the session log ends")

    main_thread = threading.main_thread()
    for thread in threading.enumerate():
        if thread is not main_thread and not thread.daemon:
            thread.join(timeout=_GRACE_SECONDS)

    survivors = [
        t for t in threading.enumerate() if t is not main_thread and t.is_alive()
    ]
    blockers = [t for t in survivors if not t.daemon]

    print(f"\n[probe] {len(survivors)} thread(s) still alive after teardown():\n")
    for thread in survivors:
        print(_describe(thread))

    if blockers:
        names = ", ".join(t.name for t in blockers)
        print(
            f"[probe] VERDICT: {len(blockers)} NON-DAEMON thread(s) hold the process open: {names}"
        )
        return 1

    print("[probe] VERDICT: no non-daemon survivor — the interpreter is free to exit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
