"""Run the probes modules declared, once per health interval (`EPIC-038D`).

A probe may ask the exchange something (`IHealthProbe`), and the snapshot must be
written on time whether or not the exchange answers. Each probe therefore measures
on a worker thread and the caller waits for it at most `wait_s`: a healthy exchange
answers inside the wait and the snapshot carries this interval's number; a slow one
costs the snapshot `wait_s` and no more, and the answer lands in the next. A probe
still running when the next interval comes is not started again, so a hung exchange
costs one thread, not one per minute.

A probe that raises is logged at WARNING the first time and quietly after that
until it works again (then one INFO line), so an exchange that is down for an hour
does not write sixty warnings.
"""

from __future__ import annotations

import logging
import threading

from Sagittarius_Elite_Warrior.src.core.contracts.i_health_probe import IHealthProbe
from Sagittarius_Elite_Warrior.src.core.contracts.i_operations_registry import (
    IHealthProbeTable,
    PortResolver,
)

logger = logging.getLogger("App.Operations.Health")

#: How long a snapshot waits for its probes before it goes out without them.
DEFAULT_WAIT_SECONDS = 5.0


class HealthProbes:
    def __init__(
        self,
        table: IHealthProbeTable,
        resolver: PortResolver,
        wait_s: float = DEFAULT_WAIT_SECONDS,
    ) -> None:
        self._table = table
        self._resolver = resolver
        self._wait_s = wait_s
        self._probes: tuple[IHealthProbe, ...] | None = None
        self._running: dict[str, threading.Thread] = {}
        self._failing: set[str] = set()
        self._lock = threading.Lock()

    def run(self) -> None:
        """Measure every probe now; never raises."""
        started = [
            thread
            for probe in self._built()
            if (thread := self._start(probe)) is not None
        ]
        for thread in started:
            thread.join(self._wait_s)

    def _built(self) -> tuple[IHealthProbe, ...]:
        """The probes, built the first time they are wanted (the container is whole by then)."""
        if self._probes is None:
            self._probes = tuple(
                descriptor.factory(self._resolver)
                for descriptor in self._table.probe_descriptors()
            )
        return self._probes

    def _start(self, probe: IHealthProbe) -> threading.Thread | None:
        with self._lock:
            held = self._running.get(probe.name)
            if held is not None and held.is_alive():
                logger.debug(
                    "[health] probe %s is still measuring; not started again",
                    probe.name,
                )
                return None
            thread = threading.Thread(
                target=self._measure,
                args=(probe,),
                name=f"HealthProbe-{probe.name}",
                daemon=True,
            )
            self._running[probe.name] = thread
        thread.start()
        return thread

    def _measure(self, probe: IHealthProbe) -> None:
        try:
            probe.measure()
        except Exception as failure:  # noqa: BLE001 - the seam: a probe's failure is logged, never raised
            self._failed(probe.name, failure)
        else:
            self._worked(probe.name)

    def _failed(self, name: str, failure: Exception) -> None:
        with self._lock:
            first = name not in self._failing
            self._failing.add(name)
        if first:
            logger.warning(
                "[health] probe %s failed; its number stays unknown until it works",
                name,
                exc_info=failure,
            )

    def _worked(self, name: str) -> None:
        with self._lock:
            recovered = name in self._failing
            self._failing.discard(name)
        if recovered:
            logger.info("[health] probe %s works again", name)
