"""`EPIC-047E` - the VPS link as Add to VPS sees it, for the Bots screen's tests: it records each request and answers as told.

Derived from `IVpsDelivery`, so a change to the port fails here (`CS-001`).
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    HostControlReply,
    HostControlRequest,
    HostControlStatus,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_vps_delivery import (
    IVpsDelivery,
)


class FakeVpsDelivery(IVpsDelivery):
    def __init__(self) -> None:
        self.sent: list[tuple[HostControlRequest, float]] = []
        self.reply = HostControlReply(
            HostControlStatus.DONE,
            "bot ab12cd was added as a DRAFT",
            "c" * 32,
            "ab12cd",
        )

    def send(self, request: HostControlRequest, wait_s: float) -> HostControlReply:
        self.sent.append((request, wait_s))
        return self.reply
