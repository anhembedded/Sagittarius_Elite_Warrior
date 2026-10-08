"""`EPIC-035A` — `IBotTicker` on a daemon thread per task.

Each task has its own thread, so a slow check never delays another. The wait is
`Event.wait(timeout)`, so `close()` ends it at once instead of after a sleep.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_ticker import (
    IBotTicker,
)

logger = logging.getLogger("App.Bots.Ticker")


class ThreadBotTicker(IBotTicker):
    """Ticks each task on its own named thread."""

    def __init__(self, name: str) -> None:
        self._name = name
        self._lock = threading.Lock()
        self._stopped = threading.Event()
        self._threads: list[threading.Thread] = []

    def every(self, seconds: float, task: Callable[[], None]) -> None:
        if seconds <= 0:
            raise ValueError(f"a ticker interval must be positive, got {seconds}")
        thread = threading.Thread(
            target=self._run,
            args=(seconds, task),
            name=f"{self._name}-{len(self._threads)}",
            daemon=True,
        )
        with self._lock:
            if self._stopped.is_set():
                logger.warning(
                    "Ticker %s is closed; a task was not started", self._name
                )
                return
            self._threads.append(thread)
        thread.start()

    def close(self) -> None:
        self._stopped.set()
        with self._lock:
            threads = tuple(self._threads)
        for thread in threads:
            if thread is not threading.current_thread():
                thread.join()

    def _run(self, seconds: float, task: Callable[[], None]) -> None:
        while not self._stopped.wait(seconds):
            try:
                task()
            except Exception:
                # A check that raised must not end the only trigger of the next.
                logger.exception("Ticker %s: a tick raised", self._name)
