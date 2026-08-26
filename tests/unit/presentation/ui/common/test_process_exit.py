"""`BUG-054` regression — `exit_process()` must never let a surviving
non-daemon worker thread hold the process open forever.

The defect this file protects against is not visible in-process: the hang
happened inside CPython's own exit sequence, after every line of application
code had already run. So these tests assert the two decisions that sequence
depends on — *does this exit take the forced path, and does it say why* —
while `tests/sanity/test_bug054_stuck_worker_exit.py` proves the process
itself actually dies. Neither is sufficient alone: a unit test cannot kill a
process, and a process test cannot show which branch was taken.
"""

from __future__ import annotations

import logging
import threading

import pytest
from Sagittarius_Elite_Warrior.src.presentation.ui.common import process_exit


@pytest.fixture
def blocked_worker():
    """A live NON-daemon thread — the exact condition that hangs exit."""
    release = threading.Event()
    thread = threading.Thread(
        target=release.wait, name="Bug054BlockedWorker", daemon=False
    )
    thread.start()
    yield thread
    release.set()
    thread.join(timeout=5)


def test_clean_exit_uses_sys_exit_when_no_worker_survives(monkeypatch) -> None:
    """The normal path must stay exactly what it was — `SystemExit` with the
    real code, no forced exit, no warning. A fix that made every shutdown
    take the forced path would skip `atexit` and buffered flushing on every
    single run, which is a worse bug than the one it replaces."""
    forced: list[int] = []
    monkeypatch.setattr(process_exit.os, "_exit", lambda code: forced.append(code))

    with pytest.raises(SystemExit) as exc_info:
        process_exit.exit_process(3)

    assert exc_info.value.code == 3
    assert forced == [], "a clean shutdown must not need os._exit()"


def test_surviving_non_daemon_thread_forces_exit_and_is_named(
    blocked_worker, monkeypatch, caplog
) -> None:
    """The reported failure: shutdown completed, `App stopped.` was logged,
    and the process never returned because a non-daemon `ThreadPoolExecutor`
    worker was still running and `concurrent.futures`' atexit hook joins it
    with no timeout.

    Before the fix this call was `sys.exit()`, which hangs in exactly that
    join. After it, the process exits with the real code AND names the
    thread — the log tail in the bug report stopped at `App stopped.` with
    nothing about what was still alive, which is why the culprit could not be
    identified from the report at all.
    """
    forced: list[int] = []
    monkeypatch.setattr(process_exit.os, "_exit", lambda code: forced.append(code))

    with caplog.at_level(logging.WARNING, logger="App.ProcessExit"):
        process_exit.exit_process(7, grace_period_sec=0.2)

    assert forced == [7], (
        "a non-daemon thread outliving shutdown must force the exit, not wait "
        "on a join that never returns"
    )
    warning = "\n".join(
        record.message for record in caplog.records if record.levelno >= logging.WARNING
    )
    assert blocked_worker.name in warning, (
        f"the forced-exit warning must name the thread that caused it:\n{warning}"
    )
    assert "BUG-054" in warning


def test_grace_period_lets_a_finishing_worker_exit_normally(monkeypatch) -> None:
    """A worker that is merely slow, not stuck, must not be cut off: the
    grace period exists so the common case (a task a few hundred ms from
    done) still takes the clean path."""
    forced: list[int] = []
    monkeypatch.setattr(process_exit.os, "_exit", lambda code: forced.append(code))

    release = threading.Event()
    thread = threading.Thread(
        target=release.wait, name="Bug054SlowWorker", daemon=False
    )
    thread.start()
    threading.Timer(0.2, release.set).start()

    with pytest.raises(SystemExit) as exc_info:
        process_exit.exit_process(0, grace_period_sec=5.0)

    thread.join(timeout=5)
    assert exc_info.value.code == 0
    assert forced == [], (
        "a worker that finished inside the grace period must not be forced"
    )


def test_daemon_threads_are_never_counted() -> None:
    """Daemon threads cannot block interpreter exit, so reporting them would
    be noise — and would make the forced path fire on healthy shutdowns (the
    UIWatchdog's own monitor thread is a daemon and is alive until teardown
    stops it)."""
    release = threading.Event()
    thread = threading.Thread(target=release.wait, name="Bug054Daemon", daemon=True)
    thread.start()
    try:
        names = [t.name for t in process_exit.surviving_worker_threads()]
        assert "Bug054Daemon" not in names
    finally:
        release.set()
        thread.join(timeout=5)
