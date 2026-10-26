"""A reader's view of the host-facts file: the last good header, how old, and whether it lives (`EPIC-047B`).

The bridge (`EPIC-047C`) holds one of these per session. A torn, missing or older file never
replaces what is held (the host's writes are atomic, so torn means damaged, not caught mid-write),
and the age is the sign that matters: a host that stopped leaves a file whose age only grows.
"""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_facts_document import (
    HostFactsHeader,
    HostFactsUnreadableError,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_host_facts_source import (
    IHostFactsSource,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_operations_clock import (
    IOperationsClock,
)

#: A host is called dead after this many of its own heartbeats without a write.
LIVE_AFTER_HEARTBEATS = 3


@dataclass(frozen=True, slots=True)
class HostFactsReading:
    #: The last good header, or `None` when none was ever read.
    header: HostFactsHeader | None
    #: Seconds since `header.written_at`; `None` without a header.
    age_s: float | None
    live: bool
    #: Why the latest look did not move the held header ("" when it did or found it unchanged).
    problem: str = ""


class HostFactsWatch:
    def __init__(self, source: IHostFactsSource, clock: IOperationsClock) -> None:
        self._source = source
        self._clock = clock
        self._held: HostFactsHeader | None = None

    def refresh(self) -> HostFactsReading:
        problem = self._look()
        held = self._held
        if held is None:
            return HostFactsReading(None, None, live=False, problem=problem)
        age_s = (self._clock.now() - held.written_at).total_seconds()
        live = age_s <= LIVE_AFTER_HEARTBEATS * held.heartbeat_s
        return HostFactsReading(held, age_s, live, problem)

    def _look(self) -> str:
        try:
            found = self._source.read_header()
        except HostFactsUnreadableError as failure:
            return f"the file is unreadable, the last good one is kept: {failure}"
        if found is None:
            return "there is no file" + (
                ", the last good one is kept" if self._held else ""
            )
        held = self._held
        if held is not None and found.revision < held.revision:
            return f"an older revision ({found.revision} < {held.revision}) was ignored"
        self._held = found
        return ""
