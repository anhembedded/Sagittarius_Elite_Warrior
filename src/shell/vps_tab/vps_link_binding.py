"""`EPIC-047E` — binds the one VPS link: for the VPS tab (`SharedVpsSession`) and for Add to VPS (`IVpsDelivery`).

@details Both are bound at the composition root and built at first use, so a run that never opens the VPS tab or sends a bot
holds no link (`SharedVpsSession` resolves the profiles and the local dispatcher only then).
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_vps_delivery import (
    IVpsDelivery,
)
from Sagittarius_Elite_Warrior.src.shell.vps_tab.shared_vps_session import (
    SharedVpsSession,
)
from Sagittarius_Elite_Warrior.src.shell.vps_tab.vps_delivery import VpsDelivery
from sagittarius_engine.interfaces.i_container import IContainer


def bind_vps_link(container: IContainer) -> None:
    shared = SharedVpsSession(container)
    container.singleton(SharedVpsSession, shared)
    container.singleton(IVpsDelivery, VpsDelivery(shared))
