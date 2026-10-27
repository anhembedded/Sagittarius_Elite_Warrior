"""Decide when the host's facts are written, and build the document (`EPIC-047B`).

The facts are looked at on a short beat (`FACTS_POLL_SECONDS`), but the file is written only when
they differ from the last written ones or when `FACTS_HEARTBEAT_SECONDS` have passed since the last
write: a quiet host is not rewritten every beat, and a reader can still tell it from a dead one by
`written_at`. The comparison is value equality of `HostHeldFacts`, so a new read that says the same
is no change.

Not thread-safe by design: exactly one worker calls `tick` (`HostFactsPublishing`). Since `EPIC-047H` the rule
itself lives in `DocumentPublisher`, shared with the two files the VPS tab adds; this is the facts file's
instance of it, with the signature it always had.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_held_facts import (
    HostHeldFacts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_host_held_facts import (
    IHostHeldFacts,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.document_publisher import (
    DocumentPublisher,
    first_revision_after,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_facts_document import (
    FACTS_HEARTBEAT_SECONDS,
    HostFactsDocument,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_host_facts_sink import (
    IHostFactsSink,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_operations_clock import (
    IOperationsClock,
)

__all__ = ["HostFactsPublisher", "first_revision_after"]


class HostFactsPublisher(DocumentPublisher[HostHeldFacts, HostFactsDocument]):
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
        super().__init__(
            held.read,
            HostFactsDocument,
            sink,
            clock,
            pid,
            first_revision,
            heartbeat_s,
        )
