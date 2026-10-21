"""`BUG-253` - the sanity shutdown check must not report a worker that is on its way out.

`ThreadPoolExecutor.shutdown(wait=False)` returns at once and the idle workers exit a moment
later, so a check taken at that instant named `ThreadPoolExecutor-0_2` on a run where nothing hung.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

from Sagittarius_Elite_Warrior.tests.sanity.leaked_threads import (
    non_daemon_threads_left_since,
)


def _ident_set() -> set[int | None]:
    return {t.ident for t in threading.enumerate()}


def test_a_pool_shut_down_without_waiting_is_not_reported_as_leaked() -> None:
    before = _ident_set()
    pool = ThreadPoolExecutor(max_workers=2)
    started = threading.Event()
    release = threading.Event()
    pool.submit(lambda: (started.set(), release.wait(5)))
    assert started.wait(5), "the worker is running"
    pool.shutdown(wait=False)
    release.set()

    assert non_daemon_threads_left_since(before) == []


def test_a_thread_that_never_ends_is_still_reported() -> None:
    before = _ident_set()
    forever = threading.Event()
    stuck = threading.Thread(target=forever.wait, name="stuck-worker")
    stuck.start()
    try:
        assert non_daemon_threads_left_since(before, grace_seconds=0.2) == [
            "stuck-worker"
        ]
    finally:
        forever.set()
        stuck.join(5)
