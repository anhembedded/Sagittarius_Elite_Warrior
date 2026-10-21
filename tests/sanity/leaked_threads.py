"""The non-daemon threads a shutdown left behind, once the ones that are leaving have left.

`BUG-253`: `IThreadManager`'s pool is shut down with `wait=False` (`app_bootstrapper.py` ->
`_log_surviving_non_daemon_threads`), so a worker told to stop is still alive for a moment after
`shutdown()` returns. A check that lists the threads at that instant reports a worker that was one
scheduling slice from exiting. The check that matters is the process's: Python's exit joins every
such worker, so a thread that is still alive after a bounded wait is the one that keeps the process
from exiting.
"""

from __future__ import annotations

import threading
import time

#: How long a worker that has been told to stop is given to leave. A hung thread uses all of it.
LEAVING_GRACE_SECONDS: float = 5.0


def non_daemon_threads_left_since(
    before: set[int | None], grace_seconds: float = LEAVING_GRACE_SECONDS
) -> list[str]:
    """Names of the threads started after `before` that are still alive after `grace_seconds`.

    Joins each new non-daemon thread against one shared deadline rather than sleeping, so a
    thread that is already gone costs nothing."""
    deadline = time.monotonic() + grace_seconds
    new = [
        t
        for t in threading.enumerate()
        if t.ident not in before
        and not t.daemon
        and t is not threading.current_thread()
    ]
    for thread in new:
        thread.join(timeout=max(0.0, deadline - time.monotonic()))
    return [t.name for t in new if t.is_alive()]
