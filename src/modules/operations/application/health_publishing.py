"""A host that keeps its health snapshot current while it lives (`EPIC-038C`).

`begin()` writes the first snapshot at once (a reader should not wait an
interval to learn there is a host), `tick()` is what the scheduler calls every
interval, `end()` writes the last one with the host `STOPPED`. After `end()` a
late tick writes nothing, so a job that fires during shutdown cannot overwrite
`STOPPED` with `SERVING`.

A write that fails (a full disk, a permission) is logged at ERROR and the host
carries on: the snapshot is a report about the work, and losing it must never
stop the work. `status` then calls the host `stale`, which is true.

With a `HealthCadence` (the `run` host, `EPIC-038D`) the state is the cadence's,
a hook runs before each periodic snapshot (the probes) and one after each (the
health line), and `end()` writes `FAILED` when the host failed and `STOPPED`
otherwise. A hook that raises is logged and the snapshot is written anyway.
Without one, everything is as it was.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from functools import partial

from Sagittarius_Elite_Warrior.src.modules.operations.application.health_cadence import (
    HealthCadence,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.health_publisher import (
    HealthPublisher,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.health_snapshot import (
    HealthSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_state import (
    HostState,
)

logger = logging.getLogger("App.Operations.Health")


class HealthPublishing:
    """`begin()` -> `tick()`* -> `end()`."""

    def __init__(
        self, publisher: HealthPublisher, cadence: HealthCadence | None = None
    ) -> None:
        self._publisher = publisher
        self._cadence = cadence
        self._lock = threading.Lock()
        self._ended = False
        if cadence is not None:
            cadence.attach(self.tick)

    def begin(self) -> None:
        self._write(self._state())

    def tick(self) -> None:
        """The periodic snapshot: probes first, then the snapshot, then the line."""
        if self._cadence is not None:
            for before in self._cadence.before_hooks:
                _guarded("before", before)
        snapshot = self._write(self._state())
        if snapshot is not None and self._cadence is not None:
            for after in self._cadence.after_hooks:
                _guarded("after", partial(after, snapshot))

    def end(self) -> None:
        with self._lock:
            if self._ended:
                return
            failed = (
                self._cadence is not None and self._cadence.state is HostState.FAILED
            )
            self._publish(HostState.FAILED if failed else HostState.STOPPED)
            self._ended = True

    def _state(self) -> HostState:
        return self._cadence.state if self._cadence is not None else HostState.SERVING

    def _write(self, host_state: HostState) -> HealthSnapshot | None:
        with self._lock:
            if self._ended:
                return None
            return self._publish(host_state)

    def _publish(self, host_state: HostState) -> HealthSnapshot | None:
        try:
            return self._publisher.publish(host_state)
        except OSError as failure:
            logger.error(
                "[health-snapshot] could not write the snapshot (%s): %s",
                host_state.value,
                failure,
            )
            return None


def _guarded(moment: str, hook: Callable[[], None]) -> None:
    """A hook is the host's business, not the snapshot's: its failure is logged, not raised."""
    try:
        hook()
    except Exception:
        logger.exception("[health-snapshot] a %s-snapshot hook failed", moment)
