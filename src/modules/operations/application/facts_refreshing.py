"""`EPIC-047H` — a host that refreshes the exchange facts for the VPS tab without ever making anything wait for it.

@details One daemon worker thread runs `FactsRefresher.step()` and sleeps the time it asks for, woken early
when a refresh is requested (`wake`). A read of the exchange can take seconds, a retry up to 3.5 s more; it
happens on this thread and on no other: not the scheduler's, not the control poller's, not a bot's. If the
worker is stuck in a read, `end()` waits `END_JOIN_SECONDS` and leaves it (a daemon thread dies with the
process), as the facts writer does (`HostFactsPublishing`).

A failure of a step is never raised into the host: the refresh is a report about the work and losing it
must not stop the work. It is logged at ERROR once per cause until a step succeeds (`FailureCause`), by kind
and errno and never by the exception's words, which may carry what a key store said; those go to DEBUG.
"""

from __future__ import annotations

import logging
import threading

from Sagittarius_Elite_Warrior.src.modules.operations.application.host_facts_publishing import (
    END_JOIN_SECONDS,
    FailureCause,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.vps_facts_refresher import (
    FactsRefresher,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.vps_refresh_work import (
    IDLE_S,
)

logger = logging.getLogger("App.Operations.VpsRefresh")


class FactsRefreshing:
    """`begin()` -> (the worker steps)* -> `end()`."""

    def __init__(
        self,
        refresher: FactsRefresher,
        wake: threading.Event,
        join_seconds: float = END_JOIN_SECONDS,
    ) -> None:
        self._refresher = refresher
        self._wake = wake
        self._join_seconds = join_seconds
        self._closed = threading.Event()
        self._worker: threading.Thread | None = None
        self._failing: FailureCause | None = None

    def begin(self) -> None:
        if self._worker is not None:
            return
        self._worker = threading.Thread(
            target=self._work, name="vps-refresh", daemon=True
        )
        self._worker.start()

    def end(self) -> None:
        self._closed.set()
        self._wake.set()
        worker, self._worker = self._worker, None
        if worker is None:
            return
        worker.join(self._join_seconds)
        if worker.is_alive():
            logger.warning(
                "[vps-refresh] the worker is still busy at shutdown; it is left behind"
            )

    def work_once(self) -> float:
        """One step and the seconds to sleep after it. Never raises (a test may call it directly)."""
        try:
            sleep_s = self._refresher.step()
        except Exception as failure:  # noqa: BLE001 - the seam to the host: the refresh must never stop the work
            self._failed(failure)
            return IDLE_S
        self._succeeded()
        return sleep_s

    def _work(self) -> None:
        while not self._closed.is_set():
            sleep_s = self.work_once()
            self._wake.wait(sleep_s)
            self._wake.clear()

    def _failed(self, failure: Exception) -> None:
        cause = FailureCause.of(failure)
        if cause == self._failing:
            return
        self._failing = cause
        logger.debug("[vps-refresh] the failure's own words", exc_info=failure)
        logger.error(
            "[vps-refresh] a refresh step failed (%s, errno %s); the tab's facts age until a step succeeds",
            cause.kind,
            cause.errno,
        )

    def _succeeded(self) -> None:
        if self._failing is None:
            return
        self._failing = None
        logger.info("[vps-refresh] refreshing again")
