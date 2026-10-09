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


#: How long `close()` waits for the worker to finish what is queued: past it the
#: app is closing with a task stuck (a network call), and it must not wait for it.
CLOSE_JOIN_SECONDS: float = 10.0


class _Stop:
    """What `close()` queues last: the worker ends when it reaches it."""


_STOP = _Stop()


class ThreadBotWorkQueue(IBotWorkQueue):
    """A FIFO queue drained by its own thread, named after the bot."""

    def __init__(self, name: str, join_timeout: float = CLOSE_JOIN_SECONDS) -> None:
        self._join_timeout = join_timeout
        self._tasks: queue.Queue[Callable[[], None] | _Stop] = queue.Queue()
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
            self._thread.join(timeout=self._join_timeout)
            if self._thread.is_alive():
                logger.warning(
                    "Worker %s did not finish within %.0f s of close; it is a "
                    "daemon thread and ends with the process",
                    self._thread.name,
                    self._join_timeout,
                )

    def _run(self) -> None:
        while True:
            task = self._tasks.get()
            if isinstance(task, _Stop):
                return
            try:
                task()
            except Exception:
                # A task that raised must not end the bot's only writer; the
                # executor turns every failure it can name into a fault itself.
                logger.exception("Worker %s: a task raised", self._thread.name)
