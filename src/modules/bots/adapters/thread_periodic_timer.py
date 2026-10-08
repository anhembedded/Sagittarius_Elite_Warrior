"""`EPIC-035B` — a daemon thread that calls one function every interval.

It drives `UserStreamWatch.check()`: the watch decides, from the bot clock it
is given, whether anything is due; this only supplies the heartbeat. A tick
that raises is logged and the next one still runs, because the watch is the
supervision of every running bot and must outlive any one bad pass.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from datetime import timedelta

logger = logging.getLogger("App.Bots.Worker")


class ThreadPeriodicTimer:
    """Calls `tick` every `interval` on its own thread, from `start()` to `stop()`."""

    def __init__(
        self, name: str, interval: timedelta, tick: Callable[[], None]
    ) -> None:
        self._name = name
        self._interval_seconds = interval.total_seconds()
        self._tick = tick
        self._stopped = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name=self._name, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """End the thread and wait for it. A tick in progress finishes first."""
        self._stopped.set()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join()

    def _run(self) -> None:
        while not self._stopped.wait(self._interval_seconds):
            try:
                self._tick()
            except Exception:
                logger.exception("Timer %s: a tick raised", self._name)
