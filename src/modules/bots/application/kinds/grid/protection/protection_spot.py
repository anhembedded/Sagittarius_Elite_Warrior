"""`EPIC-039L` — Spot has no exchange-side protection: a holding is not a leveraged exposure.

@details The implementation of `IExposureProtection` for an inventory venue. It does nothing,
so a Spot Grid's start, stop and reconcile are byte for byte what they were.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_exposure_protection import (
    IExposureProtection,
    ProtectionVerdict,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import GridPlan


class NoProtection(IExposureProtection):
    def protect(self, plan: GridPlan) -> bool:
        return True

    def supervise(self) -> ProtectionVerdict:
        return ProtectionVerdict.OK

    def describe_stop(self) -> str:
        return ""

    def release(self) -> bool:
        return True
