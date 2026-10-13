"""What `bot apply` recorded about the plan (`EPIC-038I`).

The plan file names bots by `name` and `venue`; the host starts bots by id. `bot apply`
is where the two meet: after it has created or matched each entry it records, per bot id,
what the operator wants. `run --start-planned` reads only this record (`IBotPlan`), never
the plan file the operator may since have edited but not applied.

A record holds ids, names, venues and a desired state. No parameter, no key, no account
identifier: it lives in the data root next to the health snapshot.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DesiredState(str, Enum):
    RUNNING = "running"
    STOPPED = "stopped"


class AppliedPlanUnreadableError(ValueError):
    """The record exists and cannot be read; the message says why, without its contents."""


@dataclass(frozen=True, slots=True)
class AppliedBot:
    bot_id: str
    name: str
    venue: str
    desired_state: DesiredState


@dataclass(frozen=True, slots=True)
class AppliedPlan:
    bots: tuple[AppliedBot, ...] = ()

    def desired_for(self, bot_id: str) -> DesiredState | None:
        for bot in self.bots:
            if bot.bot_id == bot_id:
                return bot.desired_state
        return None

    def wants_running(self) -> frozenset[str]:
        return frozenset(
            bot.bot_id for bot in self.bots if bot.desired_state is DesiredState.RUNNING
        )
