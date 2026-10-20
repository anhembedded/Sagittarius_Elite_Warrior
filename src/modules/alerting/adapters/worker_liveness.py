"""`IWorkerLiveness` over a stamp per worker thread (`EPIC-036E1`).

Each worker (a delivery lane, the housekeeping pass) calls `touch` after every
pass; `is_alive` is `True` while the oldest stamp is younger than `stall_after`.
Stamps use the injected `IAlertClock`, so a test moves time and never sleeps. A
worker that was never registered cannot make the answer `True`: with nothing
registered the answer is `False`.
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta

from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_clock import (
    IAlertClock,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_worker_liveness import (
    IWorkerLiveness,
)

#: A pass that has not finished in this long is a wedged worker. A healthy pass
#: takes seconds (a channel call is bounded by the transport's timeout, a queue
#: by `FillBacklog`); five minutes equals the ping interval, so a wedge costs at
#: most one more ping before the monitor's silence begins.
STALL_AFTER = timedelta(minutes=5)


class WorkerLiveness(IWorkerLiveness):
    def __init__(
        self, clock: IAlertClock, stall_after: timedelta = STALL_AFTER
    ) -> None:
        self._clock = clock
        self._stall_after = stall_after
        self._lock = threading.Lock()
        self._stamps: dict[str, datetime] = {}

    def register(self, worker: str) -> None:
        """Expect `worker` from now on; its first stamp is now."""
        self.touch(worker)

    def touch(self, worker: str) -> None:
        now = self._clock.now()
        with self._lock:
            self._stamps[worker] = now

    def is_alive(self) -> bool:
        with self._lock:
            registered = bool(self._stamps)
        return registered and not self.stalled()

    def stalled(self) -> tuple[str, ...]:
        now = self._clock.now()
        with self._lock:
            return tuple(
                worker
                for worker, stamp in self._stamps.items()
                if now - stamp > self._stall_after
            )
