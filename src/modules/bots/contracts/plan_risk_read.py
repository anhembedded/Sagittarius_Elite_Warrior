"""`EPIC-039J` — what a read of a position venue's plan-risk facts answers.

@details The facts are `PlanRiskFacts` (the account's setting for the symbol and its leverage
brackets, `bot_kind_inputs.py`). A read that could not get them says why; an unknown fact is
never an empty bracket list, because the liquidation estimate built on it would be a number
that looks measured.
"""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.core.contracts.wire_name import wire_name
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    PlanRiskFacts,
)


@wire_name("sew.plan-risk-unavailable/1")
@dataclass(frozen=True, slots=True)
class PlanRiskUnavailable:
    """Asked, and the venue did not give the facts (or has no position risk)."""

    reason: str

    def __post_init__(self) -> None:
        if not self.reason:
            raise ValueError("an unavailable read names why")


type PlanRiskRead = PlanRiskFacts | PlanRiskUnavailable
