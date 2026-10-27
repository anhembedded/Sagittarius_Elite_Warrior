"""`EPIC-047C` — the types of `operations` that cross the remote link, each under its wire name.

One root: the host-facts file as the bridge hands it to the desktop (`HostFactsDocument`: the
header the host wrote and the four groups of facts only it holds). The host-control request and
reply cross as roots of `bots`' list, where `EPIC-047A` put them.

`EPIC-047H` adds two: the market-data file (`MarketDataDocument`: live prices and forming candles) and the
host-reads file (`HostReadsDocument`: the planner inputs, the fills and the symbol rules the host read for the tab).
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.wire_root import WireRoot
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_facts_document import (
    HostFactsDocument,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_reads_document import (
    HostReadsDocument,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.market_data_document import (
    MarketDataDocument,
)

HOST_FACTS_DOCUMENT_ROOT = "sew.host-facts-document/1"
#: `EPIC-047H`: the market-data file and the host-reads file, which the host writes in their wire form.
MARKET_DATA_DOCUMENT_ROOT = "sew.market-data-document/1"
HOST_READS_DOCUMENT_ROOT = "sew.host-reads-document/1"

OPERATIONS_WIRE_ROOTS: tuple[WireRoot, ...] = (
    WireRoot(HOST_FACTS_DOCUMENT_ROOT, HostFactsDocument),
    WireRoot(MARKET_DATA_DOCUMENT_ROOT, MarketDataDocument),
    WireRoot(HOST_READS_DOCUMENT_ROOT, HostReadsDocument),
)
