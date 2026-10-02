"""`BUG-140` — the cyclic garbage collector runs on the Qt main thread only.

CPython runs a generational collection on whichever thread allocates past the
threshold. A Qt view is a reference cycle (the view holds its view-model, the
view-model's signals hold the view's slots), so only that collection frees it,
and it finalizes the Qt wrappers on the thread that ran it. On a worker thread
that tears a widget down while the main thread is inside Qt: the test process
died with `Segmentation fault` twice, once on a `concurrent.futures` pool
worker (`runner.py:268 feed`) and once on xdist's execnet receiver thread.

The policy is two calls: `stop_automatic_collection()` once, then
`collect_due_generations()` from the main thread, as often as the automatic
collector would have run. `MainThreadGarbageCollector` calls it on a timer in
the app; the root `tests/conftest.py` calls it after every test. This module
imports no Qt so that a test which never touches Qt does not load PySide6.
It is pyqtgraph's `GarbageCollector` pattern, for the same reason.
"""

from __future__ import annotations

import gc
import threading


def stop_automatic_collection() -> None:
    """Leave collection to `collect_due_generations()`. Idempotent."""
    gc.disable()


def collect_due_generations() -> None:
    """Collect each generation whose count passed CPython's own threshold.

    A close approximation of CPython's own schedule: it compares each
    generation's count with its threshold, but does not apply CPython's
    25% long-lived rule before collecting the oldest. Memory behaves as
    before; only the thread changes.

    @throws RuntimeError Called off the main thread, which is the hazard
        this function exists to avoid.
    """
    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError(
            "collect_due_generations() runs on the main thread only (BUG-140)"
        )
    young, middle, old = gc.get_count()
    young_threshold, middle_threshold, old_threshold = gc.get_threshold()
    if young <= young_threshold:
        return
    gc.collect(0)
    if middle <= middle_threshold:
        return
    gc.collect(1)
    if old <= old_threshold:
        return
    gc.collect(2)
