"""`EPIC-047E` — Add to VPS, carried over the VPS link (`IVpsDelivery`)."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    HostControlReply,
    HostControlRequest,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_vps_delivery import (
    IVpsDelivery,
)
from Sagittarius_Elite_Warrior.src.shell.vps_tab.shared_vps_session import (
    SharedVpsSession,
)


class VpsDelivery(IVpsDelivery):
    def __init__(self, shared: SharedVpsSession) -> None:
        self._shared = shared

    def send(self, request: HostControlRequest, wait_s: float) -> HostControlReply:
        return self._shared.session().deliver(request, wait_s)
