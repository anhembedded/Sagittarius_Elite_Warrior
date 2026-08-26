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
from unittest.mock import MagicMock

import pytest
from Sagittarius_Elite_Warrior.src.presentation.ui.app_bootstrapper import (
    _log_surviving_non_daemon_threads,
)


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
    app_engine = MagicMock()

    _log_surviving_non_daemon_threads(app_engine)

    app_engine.context.logger.warning.assert_called_once()
    (message,), _ = app_engine.context.logger.warning.call_args
    assert "BUG-052-test-stuck-worker" in message
    assert "1 non-daemon thread" in message


def test_stays_silent_when_no_non_daemon_thread_survives():
    app_engine = MagicMock()

    _log_surviving_non_daemon_threads(app_engine)

    app_engine.context.logger.warning.assert_not_called()


def test_the_calling_main_thread_itself_is_never_flagged():
    """The main thread is always alive at the point this runs (it's the one
    running this function) — it must never be reported as a survivor, or
    every real shutdown would false-positive."""
    app_engine = MagicMock()

    _log_surviving_non_daemon_threads(app_engine)

    if app_engine.context.logger.warning.called:
        (message,), _ = app_engine.context.logger.warning.call_args
        assert threading.main_thread().name not in message


def test_a_daemon_thread_is_never_flagged():
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

        _log_surviving_non_daemon_threads(app_engine)

        app_engine.context.logger.warning.assert_not_called()
    finally:
        release.set()
        thread.join(timeout=5)
