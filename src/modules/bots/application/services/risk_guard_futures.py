"""`EPIC-039F` - the Futures venue's risk guard: liquidation distance, plan and run.

@details The plan-time half is `futures_grid_checks.judge_futures_plan`, which estimates with
trading's `estimated_liquidation_price_in_brackets` (the one liquidation formula); the run-time
half is `futures_risk_classifier.classify_risk` over what the exchange reports. The thresholds
the classifier reads are the plan's (`PlanRiskInputs.thresholds`) for the first and this
guard's for the second: both come from the one `FuturesGridThresholds` the kind is built with.
"""

from __future__ import annotations

from datetime import datetime

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_risk_guard import IRiskGuard
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.risk_state import (
    RiskLevel,
    RiskSnapshot,
    RiskState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_grid_checks import (
    judge_futures_plan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_plan_risk_inputs import (
    PlanRiskInputs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_risk_classifier import (
    classify_risk,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    FuturesGridThresholds,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import Verdict


class FuturesRiskGuard(IRiskGuard):
    def __init__(self, thresholds: FuturesGridThresholds) -> None:
        self._thresholds = thresholds

    def judge_plan(self, inputs: PlanRiskInputs) -> tuple[Verdict, ...]:
        return judge_futures_plan(inputs)

    def watch(
        self, snapshot: RiskSnapshot, now: datetime, previous: RiskLevel
    ) -> RiskState:
        return classify_risk(snapshot, now, previous, self._thresholds)
