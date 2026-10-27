"""`EPIC-047H` — port: what the host last read from the exchange for the VPS tab, to be written to its file.

@details The read side of `ILatestExchangeReads`, the way `IHostHeldFacts` is the read side of the
facts the host remembers: `operations` writes this to `state/host-reads.json` and asks the exchange
nothing to do it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.exchange_reads import (
    HostExchangeReads,
)


class IHostExchangeReads(ABC):
    @abstractmethod
    def read(self) -> HostExchangeReads:
        """Everything held at this moment. Costs the exchange nothing."""
