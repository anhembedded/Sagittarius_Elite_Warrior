"""Which bots the operator wants running (`EPIC-038D`; the file arrives with `EPIC-038I`).

`run --start-planned` starts the bots whose plan says "running" and that are at
rest (DESIGN §5.3). The plan is a file `bot apply` writes into the bots' state
(`EPIC-038I`); until that task is done there is no such file, and the binding is
`NoBotPlan`, which wants nothing running. The host then says so at start instead
of silently starting nothing.

@par Extension cases
  · the plan file (`EPIC-038I`) - one `IBotPlan` that reads the desired state `bot apply`
    recorded, bound in place of `NoBotPlan`; the host and the start step do not change.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class IBotPlan(ABC):
    @abstractmethod
    def exists(self) -> bool:
        """Whether the operator has a plan at all (as distinct from a plan that
        wants no bot running)."""

    @abstractmethod
    def wants_running(self) -> frozenset[str]:
        """The ids of the bots the plan wants running."""
