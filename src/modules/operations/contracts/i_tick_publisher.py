"""`EPIC-047H` — port: a publisher the host's writer thread drives, one look at a time.

@details `HostFactsPublisher` (the facts file) was the only one; the market-data and host-reads files are
two more. `HostFactsPublishing` runs any of them on a worker of its own so that a slow or full disk delays
a file and nothing else.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class ITickPublisher(ABC):
    @abstractmethod
    def tick(self) -> None:
        """Look and, if the document calls for it, write. @throws Exception whatever the read or the write raises;
        the caller logs it once per cause and tries again at the next tick."""
