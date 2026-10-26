"""`EPIC-047B` — port: what only the running host holds, read now (`HostHeldFacts`).

@details Read-only and local: it asks no exchange and builds no venue. A reader runs on the
operations module's own worker thread, never on a trading thread.

@par Extension cases
  · a remote host's facts read from its file - `EPIC-047C` implements this port over the file,
    and the Bots screen's reads do not change.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_held_facts import (
    HostHeldFacts,
)


class IHostHeldFacts(ABC):
    @abstractmethod
    def read(self) -> HostHeldFacts:
        """The host's facts now. Does not raise for a venue or a bot it cannot read: that
        fact is absent or says it is unavailable."""
