"""Decide when a host document is written, and build it (`EPIC-047B`, generalised by `EPIC-047H`).

A document is looked at on a short beat, but it is written only when its payload differs from the last
written one or when `heartbeat_s` have passed since the last write: a quiet host is not rewritten every beat,
and a reader can still tell it from a dead one by the header's `written_at`. The comparison is value
equality of the payload, so a new read that says the same is no change. The host-facts file, the
market-data file and the host-reads file are three of these (`HostFactsPublisher` and the two built in
`OperationsModule`), and one rule is written once (`CS-` P3: a copy drifts).

Not thread-safe by design: exactly one worker calls `tick` (`HostFactsPublishing`).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta

from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_facts_document import (
    HostFactsHeader,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_document_sink import (
    IDocumentSink,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_operations_clock import (
    IOperationsClock,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_tick_publisher import (
    ITickPublisher,
)


def first_revision_after(previous: HostFactsHeader | None, now: datetime) -> int:
    """Where a starting host's revisions begin: above the file it finds, and above the clock's
    seconds, so deleting the file between two runs cannot make a reader that kept the last good
    revision call the new host older (a host writes at most once per second, so the revisions
    of any run stay below the seconds that have passed)."""
    floor = int(now.timestamp())
    return max(floor, previous.revision + 1) if previous is not None else floor


class DocumentPublisher[Payload, Document](ITickPublisher):
    """`tick()` looks at the payload and writes when it should; a failed write raises and is retried
    at the next tick, because the payload counts as written only after the sink returned."""

    def __init__(
        self,
        read: Callable[[], Payload],
        assemble: Callable[[HostFactsHeader, Payload], Document],
        sink: IDocumentSink[Document],
        clock: IOperationsClock,
        pid: int,
        first_revision: int,
        heartbeat_s: int,
    ) -> None:
        self._read = read
        self._assemble = assemble
        self._sink = sink
        self._clock = clock
        self._pid = pid
        self._revision = first_revision
        self._heartbeat = timedelta(seconds=heartbeat_s)
        self._heartbeat_s = heartbeat_s
        self._written: Payload | None = None
        self._written_at: datetime | None = None

    def tick(self) -> None:
        """@throws Exception Whatever the payload's reader or the sink raises."""
        looked = self._read()
        now = self._clock.now()
        if looked == self._written and not self._heartbeat_due(now):
            return
        self._sink.publish(
            self._assemble(
                HostFactsHeader(self._revision, now, self._heartbeat_s, self._pid),
                looked,
            )
        )
        self._written = looked
        self._written_at = now
        self._revision += 1

    def _heartbeat_due(self, now: datetime) -> bool:
        if self._written_at is None:
            return True
        elapsed = now - self._written_at
        # Below zero: the clock was set back; waiting for it to catch up would look like a dead host.
        return elapsed < timedelta(0) or elapsed >= self._heartbeat
