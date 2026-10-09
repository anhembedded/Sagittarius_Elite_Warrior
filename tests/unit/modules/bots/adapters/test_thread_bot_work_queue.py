"""`EPIC-029E` — a bot's one writer (ADR D9).

Tasks run one at a time, in posting order, on the queue's own named thread; a
task that raises is logged and the next one runs; `close()` runs what is
queued, then takes nothing more. Every wait is `close()`'s join, never a sleep.
"""

from __future__ import annotations

import logging
import threading

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.thread_bot_work_queue import (
    ThreadBotWorkQueue,
)

_NAME = "bot-a3f9c1"


def test_tasks_run_in_posting_order_on_the_queues_own_thread() -> None:
    queue = ThreadBotWorkQueue(_NAME)
    ran: list[tuple[int, str]] = []

    for index in range(5):
        queue.post(lambda i=index: ran.append((i, threading.current_thread().name)))
    queue.close()

    assert [index for index, _thread in ran] == [0, 1, 2, 3, 4]
    assert {thread for _index, thread in ran} == {_NAME}


def test_a_task_that_raises_is_logged_and_the_next_one_runs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    queue = ThreadBotWorkQueue(_NAME)
    ran: list[str] = []

    def fails() -> None:
        raise RuntimeError("boom")

    with caplog.at_level(logging.ERROR, logger="App.Bots.Worker"):
        queue.post(fails)
        queue.post(lambda: ran.append("after"))
        queue.close()

    assert ran == ["after"]
    assert any("a task raised" in record.getMessage() for record in caplog.records)


def test_a_task_posted_after_close_is_dropped_and_said(
    caplog: pytest.LogCaptureFixture,
) -> None:
    queue = ThreadBotWorkQueue(_NAME)
    queue.close()
    ran: list[str] = []

    with caplog.at_level(logging.WARNING, logger="App.Bots.Worker"):
        queue.post(lambda: ran.append("late"))

    assert ran == []
    assert any("dropped" in record.getMessage() for record in caplog.records)


def test_close_from_inside_a_task_does_not_wait_for_itself() -> None:
    queue = ThreadBotWorkQueue(_NAME)
    closed = threading.Event()

    def close_from_inside() -> None:
        queue.close()
        closed.set()

    queue.post(close_from_inside)

    assert closed.wait(timeout=5)


def test_close_gives_up_on_a_worker_stuck_in_a_task_and_says_so(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`EPIC-035V` (L8) — shutdown joined each worker with no timeout, so one
    task stuck on the network held the whole app open."""
    queue = ThreadBotWorkQueue(_NAME, join_timeout=0.05)
    started = threading.Event()
    release = threading.Event()
    queue.post(lambda: (started.set(), release.wait(timeout=30)))
    assert started.wait(timeout=5)
    closer = threading.Thread(target=queue.close, name="closer", daemon=True)

    with caplog.at_level(logging.WARNING, logger="App.Bots.Worker"):
        closer.start()
        closer.join(timeout=5)
        returned = not closer.is_alive()
        release.set()

    assert returned, "close() waited for the stuck task"
    assert any("did not finish" in record.getMessage() for record in caplog.records)
