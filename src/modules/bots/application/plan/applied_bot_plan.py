"""The plan the `run` host reads: the desired states `bot apply` recorded (`EPIC-038I`).

An `IBotPlan` over the record. It reads the record every time it is asked (the host asks
before it boots and again when it starts the bots), and an unreadable record is a
**problem**, never an empty plan: a host that read a damaged record as "nothing wanted"
would start nothing and say nothing.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.applied_plan import (
    AppliedPlan,
    AppliedPlanUnreadableError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_applied_plan_store import (
    IAppliedPlanStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_plan import IBotPlan


class AppliedBotPlan(IBotPlan):
    def __init__(self, store: IAppliedPlanStore) -> None:
        self._store = store

    def exists(self) -> bool:
        try:
            return self._store.read() is not None
        except AppliedPlanUnreadableError:
            return True

    def problem(self) -> str | None:
        try:
            self._store.read()
        except AppliedPlanUnreadableError as unreadable:
            return str(unreadable)
        return None

    def wants_running(self) -> frozenset[str]:
        """@raise AppliedPlanUnreadableError The record cannot be read: loud, never "nothing wanted"."""
        record: AppliedPlan | None = self._store.read()
        return record.wants_running() if record is not None else frozenset()
