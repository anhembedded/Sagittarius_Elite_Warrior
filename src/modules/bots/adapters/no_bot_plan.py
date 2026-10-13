"""The plan there is until `bot apply` writes one (`EPIC-038I`): none."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_plan import IBotPlan


class NoBotPlan(IBotPlan):
    def exists(self) -> bool:
        return False

    def wants_running(self) -> frozenset[str]:
        return frozenset()
