"""`EPIC-047C` — the types of `operations` that cross the remote link, each under its wire name.

One root: the host-facts file as the bridge hands it to the desktop (`HostFactsDocument`: the
header the host wrote and the four groups of facts only it holds). The host-control request and
reply cross as roots of `bots`' list, where `EPIC-047A` put them.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.wire_root import WireRoot
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_facts_document import (
    HostFactsDocument,
)

HOST_FACTS_DOCUMENT_ROOT = "sew.host-facts-document/1"

OPERATIONS_WIRE_ROOTS: tuple[WireRoot, ...] = (
    WireRoot(HOST_FACTS_DOCUMENT_ROOT, HostFactsDocument),
)
