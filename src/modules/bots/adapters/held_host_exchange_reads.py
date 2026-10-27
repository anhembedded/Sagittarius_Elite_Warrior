"""`EPIC-047H` — `IHostExchangeReads` over the memory the refresh writes."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.exchange_reads import (
    HostExchangeReads,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_host_exchange_reads import (
    IHostExchangeReads,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_latest_exchange_reads import (
    ILatestExchangeReads,
)


class HeldHostExchangeReads(IHostExchangeReads):
    def __init__(self, latest: ILatestExchangeReads) -> None:
        self._latest = latest

    def read(self) -> HostExchangeReads:
        return self._latest.latest()
