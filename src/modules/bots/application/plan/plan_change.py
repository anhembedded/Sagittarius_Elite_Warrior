"""What applying a plan does to one bot, as a value (`EPIC-038I`)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.bot_plan_document import (
    PlannedBot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.applied_plan import (
    DesiredState,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class ChangeAction(str, Enum):
    CREATE = "create"
    EDIT = "edit"
    DELETE = "delete"
    LEAVE = "leave"
    #: The plan asks for something the lifecycle table or the plan's own identity rule
    #: refuses ("needs stop first"). Nothing is done for this entry; the others go on.
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class PlanChange:
    action: ChangeAction
    name: str
    venue: TradingVenue
    #: The stored bot it concerns; `None` for a create.
    bot_id: str | None
    #: A sentence for the operator: why, and what `desired_state` will mean.
    detail: str
    #: The plan entry; `None` for a bot the plan does not name.
    planned: PlannedBot | None = None
    #: What the record says now (or the bot's state implies), and what the plan says.
    desired_before: DesiredState | None = None
    desired_after: DesiredState | None = None
    state: str | None = None

    @property
    def is_change(self) -> bool:
        """Whether applying changes anything: a bot, or what the record says of it."""
        if self.action in (ChangeAction.CREATE, ChangeAction.EDIT, ChangeAction.DELETE):
            return True
        if self.action is ChangeAction.BLOCKED:
            return False
        return (
            self.desired_after is not None
            and self.desired_before is not self.desired_after
        )


@dataclass(frozen=True, slots=True)
class PlanDiff:
    changes: tuple[PlanChange, ...]

    @property
    def has_changes(self) -> bool:
        return any(change.is_change for change in self.changes)

    @property
    def blocked(self) -> tuple[PlanChange, ...]:
        return tuple(c for c in self.changes if c.action is ChangeAction.BLOCKED)
