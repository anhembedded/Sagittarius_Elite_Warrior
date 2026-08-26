"""Process-exit guard — the last thing the application does, and the one
step that used to have no owner at all.

`BUG-054`: `teardown()` ran to completion, `App stopped.` was logged, and
then the process simply never returned. Nothing was hung *inside* shutdown;
the hang came after it, in CPython's own exit sequence. Both background
worker pools this application runs on — the Engine's `ThreadManager` and its
`TaskManager` — are `ThreadPoolExecutor`s, whose worker threads are
non-daemon, and both are shut down with `wait=False` so that a slow task
cannot stall the shutdown sequence. `wait=False` returns immediately, but
`concurrent.futures.thread` registers an `atexit` hook that **joins every
worker thread with no timeout**, so a single task still running when the
interpreter starts exiting blocks the process forever — after the last log
line, with nothing written about why.

This module makes that failure mode bounded and named instead of silent and
infinite:

1. Give any surviving non-daemon thread a short grace period to finish on
   its own — the common case is a task that is nearly done.
2. If any is still alive after it, log **which** thread and **where** it is
   (`WARNING`, with the thread's own stack) so the next occurrence names its
   culprit instead of leaving a dead log tail.
3. Exit anyway, with the real exit code, via `os._exit()` — the one call
   that does not wait on those joins.

Step 3 is deliberately last, not first: `os._exit()` skips `atexit` hooks and
buffered-output flushing, so it is reached only when the normal path has
already been proven unusable, and only after this module has flushed the
logging handlers itself.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
import time
import traceback

logger = logging.getLogger("App.ProcessExit")

#: How long a surviving non-daemon thread is given to finish on its own
#: before the process stops waiting for it. Long enough for a task that is
#: genuinely wrapping up, short enough that a human never sits in front of a
#: window that will not close.
_DEFAULT_GRACE_PERIOD_SECONDS = 5.0

#: How often the grace period re-checks, instead of sleeping through it.
_POLL_INTERVAL_SECONDS = 0.1


def surviving_worker_threads() -> list[threading.Thread]:
    """Every live non-daemon thread that would block interpreter exit.

    The main thread itself is excluded — it is the one asking. Daemon threads
    are excluded because CPython does not join them at exit, so they cannot
    cause `BUG-054`'s hang.
    """
    current = threading.current_thread()
    return [
        thread
        for thread in threading.enumerate()
        if thread is not current and thread.is_alive() and not thread.daemon
    ]


def describe_threads(threads: list[threading.Thread]) -> str:
    """One diagnostic block per thread: its name, its id, and its stack.

    The stack is the part that matters. `BUG-054`'s log ended at
    `App stopped.` with no indication of what was still running; a thread
    name alone (`ThreadPoolExecutor-0_1`) would barely improve on that, while
    its frames name the actual task.
    """
    frames = sys._current_frames()
    blocks: list[str] = []
    for thread in threads:
        stack = frames.get(thread.ident or -1)
        rendered = (
            "".join(traceback.format_stack(stack))
            if stack is not None
            else "  <stack unavailable — thread finished while being reported>\n"
        )
        blocks.append(f"  - {thread.name} (id={thread.ident}):\n{rendered}")
    return "\n".join(blocks)


def exit_process(
    exit_code: int,
    *,
    grace_period_sec: float = _DEFAULT_GRACE_PERIOD_SECONDS,
) -> None:
    """Terminate the process with `exit_code`, whatever is still running.

    Returns only in the sense that `sys.exit()` "returns" — it raises
    `SystemExit` on the clean path, and never returns at all on the forced
    one.
    """
    threads = surviving_worker_threads()
    if not threads:
        sys.exit(exit_code)

    logger.info(
        f"[process-exit] {len(threads)} non-daemon thread(s) still alive after "
        f"shutdown: {', '.join(thread.name for thread in threads)} — waiting up "
        f"to {grace_period_sec:.1f}s for them to finish."
    )

    deadline = time.monotonic() + grace_period_sec
    while time.monotonic() < deadline:
        threads = surviving_worker_threads()
        if not threads:
            logger.info(
                "[process-exit] all non-daemon threads finished within the grace "
                "period; exiting normally."
            )
            sys.exit(exit_code)
        time.sleep(_POLL_INTERVAL_SECONDS)

    logger.warning(
        f"[process-exit] {len(threads)} non-daemon thread(s) outlived shutdown by "
        f"more than {grace_period_sec:.1f}s and would block interpreter exit "
        f"forever (BUG-054). Forcing exit with code {exit_code}. Still running:\n"
        f"{describe_threads(threads)}"
    )
    _flush_diagnostics()
    os._exit(exit_code)


def _flush_diagnostics() -> None:
    """Push the warning above out of every buffer before `os._exit()` skips
    the `atexit` hooks that would normally do it.

    Deliberately NOT `logging.shutdown()`: that closes every handler process
    wide, which is correct for a process about to die and actively harmful
    anywhere else — a test that exercises this path with `os._exit` patched
    out would tear down logging for everything that runs after it.
    """
    for handler in logging.getLogger().handlers:
        try:
            handler.flush()
        except (OSError, ValueError):
            # A closed or broken handler must not stop the remaining ones from
            # flushing — the whole point of this pass is getting the warning out.
            continue
    sys.stdout.flush()
    sys.stderr.flush()
