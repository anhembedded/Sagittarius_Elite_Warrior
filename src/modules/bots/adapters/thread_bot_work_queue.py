"""`EPIC-029E` — `IBotWorkQueue` on one daemon thread per bot (ADR D9)."""

from __future__ import annotations

import logging
import queue
import threading
from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_work_queue import (
    IBotWorkQueue,
)

logger = logging.getLogger("App.Bots.Worker")

_STOP = object()


class ThreadBotWorkQueue(IBotWorkQueue):
    """A FIFO queue drained by its own thread, named after the bot."""

    def __init__(self, name: str) -> None:
        self._tasks: queue.Queue[Callable[[], None] | object] = queue.Queue()
        self._closed = False
        self._thread = threading.Thread(target=self._run, name=name, daemon=True)
        self._thread.start()

    def post(self, task: Callable[[], None]) -> None:
        if self._closed:
            logger.warning("Worker %s is closed; a task was dropped", self._thread.name)
            return
        self._tasks.put(task)

    def close(self) -> None:
        self._closed = True
        self._tasks.put(_STOP)
        if threading.current_thread() is not self._thread:
            self._thread.join()

    def _run(self) -> None:
        while True:
            task = self._tasks.get()
            if task is _STOP:
                return
            try:
                task()  # type: ignore[operator]
            except Exception:
                # A task that raised must not end the bot's only writer; the
                # executor turns every failure it can name into a fault itself.
                logger.exception("Worker %s: a task raised", self._thread.name)
