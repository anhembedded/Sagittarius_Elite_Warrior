"""`EPIC-039F` - the risk guard: one port, asked at plan time and at run time.

@details Two questions about the same risk. **Plan time** (`judge_plan`): would this ladder be
liquidated before it is used? An estimate, said to be one. **Run time** (`watch`): how close is
the exchange's own liquidation price to the mark now? A report, not an estimate.

Every venue profile answers (Liskov): Spot's guard has nothing to judge and answers `()` and
SAFE, so no caller branches on the market. The guard never changes a parameter: it refuses,
warns or reports.

Plausible extensions, each a local change: a margin-ratio input to `watch` once an account
read provides it (`MARGIN_LOW`); Cross margin's other-positions terms in `judge_plan`; a new
risk is a new check in `futures_grid_checks.py`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.risk_state import (
    RiskLevel,
    RiskSnapshot,
    RiskState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_plan_risk_inputs import (
    PlanRiskInputs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import Verdict


class IRiskGuard(ABC):
    @abstractmethod
    def judge_plan(self, inputs: PlanRiskInputs) -> tuple[Verdict, ...]:
        """@return The risk verdicts of a plan, in a fixed order; `()` where the venue
        has no such risk."""

    @abstractmethod
    def watch(
        self, snapshot: RiskSnapshot, now: datetime, previous: RiskLevel
    ) -> RiskState:
        """@return The state the exchange's `snapshot` puts a running bot in at `now`,
        given the level it was in (hysteresis)."""
