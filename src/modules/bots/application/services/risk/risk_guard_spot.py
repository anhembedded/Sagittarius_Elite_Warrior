"""`EPIC-039F` - Spot's risk guard: there is no liquidation to judge.

@details Every venue profile answers the port (Liskov), so a caller never asks which market
it is on. Spot's plan verdicts are the empty tuple - the Spot journeys' expected verdict lists
are unchanged - and its run-time state is SAFE with the reason said.
"""

from __future__ import annotations

from datetime import datetime

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_risk_guard import IRiskGuard
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.risk_state import (
    RiskLevel,
    RiskSnapshot,
    RiskState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_plan_risk_inputs import (
    PlanRiskInputs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import Verdict


class SpotRiskGuard(IRiskGuard):
    def judge_plan(self, inputs: PlanRiskInputs) -> tuple[Verdict, ...]:
        return ()

    def watch(
        self, snapshot: RiskSnapshot, now: datetime, previous: RiskLevel
    ) -> RiskState:
        return RiskState(RiskLevel.SAFE, "Spot has no liquidation")
