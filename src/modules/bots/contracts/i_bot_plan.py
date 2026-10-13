"""Which bots the operator wants running (`EPIC-038D`; the plan arrives with `EPIC-038I`).

`run --start-planned` starts the bots whose plan says "running" and that are at
rest (DESIGN §5.3). The plan is the record `bot apply` writes into the data root's
state (`AppliedBotPlan`): the host never reads the plan file the operator edits,
only what was applied.

Three answers, and the host treats each differently: **no plan** (`exists()` is
false) and **a plan it cannot read** (`problem()` is a sentence) both refuse
`--start-planned` before anything boots, because starting nothing silently is the
wrong thing; a plan that wants no bot running is a plan, and says so.

@par Extension cases
  · a second source of desired states (a file the host watches) - another `IBotPlan`; the
    host and the start step do not change.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class IBotPlan(ABC):
    @abstractmethod
    def exists(self) -> bool:
        """Whether the operator has a plan at all (as distinct from a plan that
        wants no bot running)."""

    @abstractmethod
    def problem(self) -> str | None:
        """Why the plan cannot be read, in a sentence that repeats none of its content,
        or `None` when it can be (or when there is none)."""

    @abstractmethod
    def wants_running(self) -> frozenset[str]:
        """The ids of the bots the plan wants running.

        @raise AppliedPlanUnreadableError `problem()` is not `None`: an unreadable plan is
            never read as one that wants nothing.
        """
