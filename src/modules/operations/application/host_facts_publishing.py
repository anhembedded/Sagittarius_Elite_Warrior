"""A host that keeps its facts file current without ever waiting on it (`EPIC-047B`).

The scheduler's thread calls `tick()` every `FACTS_POLL_SECONDS`; all `tick()` does is raise a flag.
One daemon worker thread does the rest - reads the host's facts (which take a lock the trading
session also takes, and may ask a keyring), compares, writes - so a slow or full disk, or a read
that hangs, delays the file and nothing else: not an order, not a stop, not the health snapshot that
shares the scheduler's clock. A write in flight is never joined by a second one: the flag is one
bit, so a stuck write costs one thread and the next look happens when it returns.

A failure is never raised: the file is a report about the work and losing it must not stop the work.
It is logged at ERROR once per cause (`FailureCause`) until a write succeeds, which is logged once
at INFO; the reason is the failure's kind and errno, never its text, because a reader's exception
may carry what a key store said. The text goes to DEBUG.

@par Threads
`begin`, `tick` and `end` come from the host's threads and touch only an `Event`; `write_now` runs
on the worker (a test may call it directly) and is the only caller of the publisher.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_tick_publisher import (
    ITickPublisher,
)

logger = logging.getLogger("App.Operations.HostFacts")

#: How long `end()` waits for a worker stuck in a write before it leaves it (a daemon thread).
END_JOIN_SECONDS = 2.0


@dataclass(frozen=True, slots=True)
class FailureCause:
    """What makes two failures one: the exception's type and, for the system's, its errno."""

    kind: str
    errno: int | None

    @staticmethod
    def of(failure: Exception) -> FailureCause:
        return FailureCause(
            type(failure).__name__,
            failure.errno if isinstance(failure, OSError) else None,
        )


class HostFactsPublishing:
    """`begin()` -> `tick()`* -> `end()`.

    @par One worker per file
    `EPIC-047H` runs the market-data and host-reads files on the same class, each with a worker of its own
    (`name` is its thread's and its log lines' name for what it writes), so one file's slow disk never holds another."""

    def __init__(
        self,
        publisher: ITickPublisher,
        join_seconds: float = END_JOIN_SECONDS,
        name: str = "host-facts",
    ) -> None:
        self._publisher = publisher
        self._join_seconds = join_seconds
        self._name = name
        self._wake = threading.Event()
        self._closed = threading.Event()
        self._worker: threading.Thread | None = None
        self._failing: FailureCause | None = None

    def begin(self) -> None:
        """Start the worker and ask for the first write at once."""
        if self._worker is not None:
            return
        self._worker = threading.Thread(
            target=self._work, name=f"{self._name}-writer", daemon=True
        )
        self._worker.start()
        self._wake.set()

    def tick(self) -> None:
        """Ask for a look. Never blocks."""
        self._wake.set()

    def end(self) -> None:
        """Stop looking. The file is left as it is: its age is the sign the host is gone."""
        self._closed.set()
        self._wake.set()
        worker, self._worker = self._worker, None
        if worker is None:
            return
        worker.join(self._join_seconds)
        if worker.is_alive():
            logger.warning(
                "[%s] the writer is still busy at shutdown; it is left behind",
                self._name,
            )

    def write_now(self) -> None:
        """One look and, if the facts call for it, one write. Never raises."""
        if self._closed.is_set():
            return
        try:
            self._publisher.tick()
        except Exception as failure:  # noqa: BLE001 - the seam to the host: the file must never stop the work
            self._failed(failure)
        else:
            self._succeeded()

    def _work(self) -> None:
        while True:
            self._wake.wait()
            if self._closed.is_set():
                return
            self._wake.clear()
            self.write_now()

    def _failed(self, failure: Exception) -> None:
        cause = FailureCause.of(failure)
        if cause == self._failing:
            return
        self._failing = cause
        logger.debug("[%s] the failure's own words", self._name, exc_info=failure)
        logger.error(
            "[%s] could not write the file (%s, errno %s); it is stale until a write succeeds",
            self._name,
            cause.kind,
            cause.errno,
        )

    def _succeeded(self) -> None:
        if self._failing is None:
            return
        self._failing = None
        logger.info("[%s] writing the file again", self._name)
