"""
`BUG-052` regression — `_log_surviving_non_daemon_threads` must name any
non-daemon thread still alive right after `app_engine.stop()` returns.

`teardown()` returning is not the same as the *process* being able to exit:
CPython's `concurrent.futures.thread` module registers its own
`_python_exit()` atexit hook at import time, which unconditionally joins
every worker thread ever created by any `ThreadPoolExecutor` in the process —
ignoring whatever `wait=` was passed to that pool's own `.shutdown()` call
(`sagittarius_engine`'s `ThreadManagerExtension.shutdown()` always passes
`wait=False`, precisely so its own step never blocks). If one of those
threads never returns (a task with no cooperative cancellation, stuck in a
blocking call), the interpreter hangs *after* `main()`'s own frame has
unwound, with no further log line — this exact mechanism is what `BUG-041`
already root-caused for one specific task; `BUG-052` reproduced the same
"App stopped. printed, process never returns" symptom from a different,
never-identified task, its own report noting the existing log had "ended
before the hang point, so it's useless for this." This module proves the
diagnostic that closes that gap, fast and in-process — the real process
boundary (does a survivor truly stop `sys.exit()` from returning) is
`sagittarius_engine`'s own, already-verified `_python_exit()` behavior
(stdlib, not this app's code to re-prove), not something worth a slow
subprocess test here.
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

import pytest
from Sagittarius_Elite_Warrior.src.presentation.ui.app_bootstrapper import (
    _log_surviving_non_daemon_threads,
)

_ENUMERATE = (
    "Sagittarius_Elite_Warrior.src.presentation.ui.app_bootstrapper.threading.enumerate"
)


@pytest.fixture
def only_these_threads():
    """Narrows `threading.enumerate()` to the threads a test actually owns.

    The function under test reads whole-process state, so an assertion about
    *absence* — "no survivor, therefore no warning" — is an assertion about
    every other test in the session. It held only by luck: one leaked
    `ThreadPoolExecutor` worker elsewhere in the suite (its workers are
    non-daemon and outlive the test that submitted to them, which is the very
    hazard this diagnostic exists to report) turned all three
    absence-asserting tests red at once, in a run whose only change was test
    ordering. Feeding the enumeration explicitly makes each case describe its
    own scenario. The main thread is always included, because the real call
    always sees it and excluding it is part of what these tests check.

    The real, unpatched enumeration is still covered — by the surviving-thread
    test below, and end-to-end by
    `tests/integration/presentation/test_shutdown_lingering_thread_diagnostic.py`.
    """

    def _use(*threads: threading.Thread):
        return patch(_ENUMERATE, return_value=[threading.main_thread(), *threads])

    return _use


@pytest.fixture
def live_thread():
    """Factory for real, started, non-daemon threads, all released at teardown.

    They have to be genuinely running: the diagnostic filters on
    `is_alive()`, so a constructed-but-never-started `Thread` is silently not
    a survivor and would make a test pass while proving nothing.
    """
    release = threading.Event()
    threads: list[threading.Thread] = []

    def _make(name: str) -> threading.Thread:
        thread = threading.Thread(target=release.wait, name=name, daemon=False)
        thread.start()
        threads.append(thread)
        return thread

    try:
        yield _make
    finally:
        release.set()
        for thread in threads:
            thread.join(timeout=5)


@pytest.fixture
def stuck_worker():
    """A real non-daemon thread blocked on an `Event`, standing in for a
    `ThreadPoolExecutor` worker running a task with no cooperative
    cancellation — exactly the shape `BUG-041`/`BUG-052` both describe.
    Always released and joined at teardown so this test can never itself
    leave a real non-daemon thread alive (which would hang the test
    process's own exit, the same class of bug this file is testing for)."""
    release = threading.Event()
    thread = threading.Thread(
        target=release.wait, name="BUG-052-test-stuck-worker", daemon=False
    )
    thread.start()
    try:
        yield thread
    finally:
        release.set()
        thread.join(timeout=5)


def test_logs_a_warning_naming_a_surviving_non_daemon_thread(stuck_worker):
    """Runs against the real, unpatched `threading.enumerate()`.

    Asserts only that the survivor is named, never how many there are: any
    other live non-daemon thread in the session is a legitimate survivor this
    diagnostic is right to report, so a count would be asserting about the
    rest of the suite rather than about this thread.
    """
    app_engine = MagicMock()

    _log_surviving_non_daemon_threads(app_engine)

    app_engine.context.logger.warning.assert_called_once()
    (message,), _ = app_engine.context.logger.warning.call_args
    assert "BUG-052-test-stuck-worker" in message
    assert "non-daemon thread(s) still alive" in message


def test_counts_and_names_every_survivor(only_these_threads, live_thread):
    first = live_thread("BUG-052-test-first")
    second = live_thread("BUG-052-test-second")

    app_engine = MagicMock()
    with only_these_threads(first, second):
        _log_surviving_non_daemon_threads(app_engine)

    (message,), _ = app_engine.context.logger.warning.call_args
    assert "2 non-daemon thread(s)" in message
    assert "BUG-052-test-first" in message
    assert "BUG-052-test-second" in message


def test_stays_silent_when_no_non_daemon_thread_survives(only_these_threads):
    app_engine = MagicMock()

    with only_these_threads():
        _log_surviving_non_daemon_threads(app_engine)

    app_engine.context.logger.warning.assert_not_called()


def test_the_calling_main_thread_itself_is_never_flagged(
    only_these_threads, live_thread
):
    """The main thread is always alive at the point this runs (it's the one
    running this function) — it must never be reported as a survivor, or
    every real shutdown would false-positive.

    Paired with one real survivor, so the assertion is that the main thread is
    filtered out of a warning that was genuinely emitted. On its own it would
    pass for the wrong reason: no warning at all also contains no name.
    """
    other = live_thread("BUG-052-test-other")

    app_engine = MagicMock()
    with only_these_threads(other):
        _log_surviving_non_daemon_threads(app_engine)

    (message,), _ = app_engine.context.logger.warning.call_args
    assert "BUG-052-test-other" in message
    assert threading.main_thread().name not in message


def test_a_daemon_thread_is_never_flagged(only_these_threads):
    """A daemon thread (e.g. AsyncRuntimeLoop, UIWatchdogMonitorThread — see
    `ui_watchdog.py`) never blocks process exit on its own; only non-daemon
    survivors matter here."""
    release = threading.Event()
    thread = threading.Thread(
        target=release.wait, name="BUG-052-test-daemon-worker", daemon=True
    )
    thread.start()
    try:
        app_engine = MagicMock()

        with only_these_threads(thread):
            _log_surviving_non_daemon_threads(app_engine)

        app_engine.context.logger.warning.assert_not_called()
    finally:
        release.set()
        thread.join(timeout=5)


def _blocked_in_a_function_with_a_findable_name(release: threading.Event) -> None:
    """Named so the stack assertion below can look for something specific.

    A test that only asserted "the message got longer" would pass on a stack
    dump pointing at the wrong thread.
    """
    release.wait()


def test_the_warning_says_where_each_survivor_is_stuck(only_these_threads):
    """BUG-059's actual blocker: the diagnostic named the thread but not the
    task, and a pool assigns one name to every task it ever runs. Without a
    stack, `'ThreadPoolExecutor-3_0'` narrows the culprit to "something that
    used the pool" — which is everything.
    """
    release = threading.Event()
    thread = threading.Thread(
        target=_blocked_in_a_function_with_a_findable_name,
        args=(release,),
        name="BUG-059-stack-probe",
        daemon=False,
    )
    thread.start()
    try:
        app_engine = MagicMock()
        with only_these_threads(thread):
            _log_surviving_non_daemon_threads(app_engine)
    finally:
        release.set()
        thread.join(timeout=5)

    (message,), _ = app_engine.context.logger.warning.call_args
    assert "BUG-059-stack-probe" in message
    assert "_blocked_in_a_function_with_a_findable_name" in message, (
        "the stack must name the function the thread is blocked in, "
        f"not just the thread — got:\n{message}"
    )


def test_a_thread_with_no_python_frame_is_reported_rather_than_dropped(
    only_these_threads,
):
    """A thread blocked inside a C call has no Python frame. Silently
    skipping it would lose exactly the survivor most likely to be stuck in a
    blocking syscall — `run_vacuum`'s SQLite VACUUM being the known example
    (see the 19-submit-site cancellation audit)."""
    dead = threading.Thread(target=lambda: None, name="BUG-059-no-frame")
    dead.start()
    dead.join(timeout=5)  # finished, so it owns no frame

    app_engine = MagicMock()
    with patch.object(dead, "is_alive", return_value=True), only_these_threads(dead):
        _log_surviving_non_daemon_threads(app_engine)

    (message,), _ = app_engine.context.logger.warning.call_args
    assert "BUG-059-no-frame" in message
    assert "no Python frame" in message
