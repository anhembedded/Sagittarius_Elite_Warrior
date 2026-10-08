"""`EPIC-035C` — `IBotRetryScheduler` on daemon `threading.Timer`s."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from datetime import timedelta

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_retry_scheduler import (
    IBotRetryScheduler,
)

logger = logging.getLogger("App.Bots.Worker")


class TimerBotRetryScheduler(IBotRetryScheduler):
    """One timer thread per pending retry; at most a handful exist at a time."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pending: set[threading.Thread] = set()
        self._closed = False

    def after(self, delay: timedelta, task: Callable[[], None]) -> None:
        with self._lock:
            if self._closed:
                logger.info("The retry scheduler is closed; a retry was dropped")
                return
            timer = threading.Timer(delay.total_seconds(), self._run, args=(task,))
            timer.daemon = True
            self._pending.add(timer)
            timer.start()

    def close(self) -> None:
        with self._lock:
            self._closed = True
            pending, self._pending = self._pending, set()
        for timer in pending:
            if isinstance(timer, threading.Timer):
                timer.cancel()

    def _run(self, task: Callable[[], None]) -> None:
        with self._lock:
            self._pending.discard(threading.current_thread())
        try:
            task()
        except Exception:
            # A timer thread has no caller to tell; the task only posts to a
            # bot's queue, so this is a closed queue or a bug worth a record.
            logger.exception("A scheduled retry raised")
