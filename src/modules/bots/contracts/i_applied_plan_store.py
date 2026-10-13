"""Where the applied plan is kept (`EPIC-038I`)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.applied_plan import (
    AppliedPlan,
)


class IAppliedPlanStore(ABC):
    @abstractmethod
    def read(self) -> AppliedPlan | None:
        """The record, or `None` when no plan was ever applied.

        @raise AppliedPlanUnreadableError A record exists and cannot be read.
        """

    @abstractmethod
    def write(self, plan: AppliedPlan) -> None:
        """Replace the record, atomically: a reader sees the old one or the new one."""
