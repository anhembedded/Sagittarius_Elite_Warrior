"""Decide when the host's facts are written, and build the document (`EPIC-047B`).

The facts are looked at on a short beat (`FACTS_POLL_SECONDS`), but the file is written only when
they differ from the last written ones or when `FACTS_HEARTBEAT_SECONDS` have passed since the last
write: a quiet host is not rewritten every beat, and a reader can still tell it from a dead one by
`written_at`. The comparison is value equality of `HostHeldFacts`, so a new read that says the same
is no change.

Not thread-safe by design: exactly one worker calls `tick` (`HostFactsPublishing`).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_held_facts import (
    HostHeldFacts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_host_held_facts import (
    IHostHeldFacts,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_facts_document import (
    FACTS_HEARTBEAT_SECONDS,
    HostFactsDocument,
    HostFactsHeader,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_host_facts_sink import (
    IHostFactsSink,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_operations_clock import (
    IOperationsClock,
)


def first_revision_after(previous: HostFactsHeader | None, now: datetime) -> int:
    """Where a starting host's revisions begin: above the file it finds, and above the clock's
    seconds, so deleting the file between two runs cannot make a reader that kept the last good
    revision call the new host older (a host writes at most once per two seconds, so the revisions
    of any run stay below the seconds that have passed)."""
    floor = int(now.timestamp())
    return max(floor, previous.revision + 1) if previous is not None else floor


class HostFactsPublisher:
    """`tick()` looks at the facts and writes when it should; a failed write raises and is retried
    at the next tick, because the facts count as written only after the sink returned."""

    def __init__(
        self,
        held: IHostHeldFacts,
        sink: IHostFactsSink,
        clock: IOperationsClock,
        pid: int,
        first_revision: int,
        heartbeat_s: int = FACTS_HEARTBEAT_SECONDS,
    ) -> None:
        self._held = held
        self._sink = sink
        self._clock = clock
        self._pid = pid
        self._revision = first_revision
        self._heartbeat = timedelta(seconds=heartbeat_s)
        self._heartbeat_s = heartbeat_s
        self._written: HostHeldFacts | None = None
        self._written_at: datetime | None = None

    def tick(self) -> None:
        """@throws Exception Whatever the facts' reader or the sink raises."""
        looked = self._held.read()
        now = self._clock.now()
        if looked == self._written and not self._heartbeat_due(now):
            return
        self._sink.publish(
            HostFactsDocument(
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
