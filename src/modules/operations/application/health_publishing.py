"""A host that keeps its health snapshot current while it lives (`EPIC-038C`).

`begin()` writes the first snapshot at once (a reader should not wait an
interval to learn there is a host), `tick()` is what the scheduler calls every
interval, `end()` writes the last one with the host `STOPPED`. After `end()` a
late tick writes nothing, so a job that fires during shutdown cannot overwrite
`STOPPED` with `SERVING`.

A write that fails (a full disk, a permission) is logged at ERROR and the host
carries on: the snapshot is a report about the work, and losing it must never
stop the work. `status` then calls the host `stale`, which is true.
"""

from __future__ import annotations

import logging
import threading

from Sagittarius_Elite_Warrior.src.modules.operations.application.health_publisher import (
    HealthPublisher,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_state import (
    HostState,
)

logger = logging.getLogger("App.Operations.Health")


class HealthPublishing:
    """`begin()` -> `tick()`* -> `end()`."""

    def __init__(self, publisher: HealthPublisher) -> None:
        self._publisher = publisher
        self._lock = threading.Lock()
        self._ended = False

    def begin(self) -> None:
        self._write(HostState.SERVING)

    def tick(self) -> None:
        self._write(HostState.SERVING)

    def end(self) -> None:
        with self._lock:
            if self._ended:
                return
            self._publish(HostState.STOPPED)
            self._ended = True

    def _write(self, host_state: HostState) -> None:
        with self._lock:
            if not self._ended:
                self._publish(host_state)

    def _publish(self, host_state: HostState) -> None:
        try:
            self._publisher.publish(host_state)
        except OSError as failure:
            logger.error(
                "[health-snapshot] could not write the snapshot (%s): %s",
                host_state.value,
                failure,
            )
