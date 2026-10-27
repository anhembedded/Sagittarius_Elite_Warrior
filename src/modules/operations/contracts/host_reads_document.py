"""`EPIC-047H` — the file of what the host last read from the exchange for the tab, besides the facts file.

@details `state/host-reads.json`: the planner's inputs and the fills of each bot and the symbol rules, each
with the moment the host read it (`HostExchangeReads`). Same header, same atomic owner-only write and same
liveness rule as the host-facts file (`HostFactsHeader`); written when a refresh changed something and at
the heartbeat. A bot with no entry was never read: the tab says "not published by the host".
"""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.exchange_reads import (
    HostExchangeReads,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_facts_document import (
    HostFactsHeader,
)

HOST_READS_FILE_NAME = "host-reads.json"
#: Seconds between two looks at what the refresh read; a change reaches the file within this.
HOST_READS_POLL_SECONDS = 5
HOST_READS_HEARTBEAT_SECONDS = 30


@dataclass(frozen=True, slots=True)
class HostReadsDocument:
    header: HostFactsHeader
    reads: HostExchangeReads
