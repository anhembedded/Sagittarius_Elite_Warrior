"""`EPIC-034H` — where a bot stands on its way to Start, as one value.

A bot reaches Start through three steps (decision D1): **Connect** (its
venue's account is read), **Design** (every constraint on the plan holds) and
**Run** (nothing else stands in the way). A `BotReadiness` holds each step's
status and every item still open, each with the reason in words and the fix:
what to do about it, and where. The Bots screen shows exactly this, and the
Start use case refuses exactly this, so the two cannot disagree
(`assessment.py` is the one function that builds it).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotRefusal,
)


class ReadinessStep(str, Enum):
    CONNECT = "Connect"
    DESIGN = "Design"
    RUN = "Run"


class StepStatus(str, Enum):
    #: Nothing left in this step, and every step before it is done.
    DONE = "DONE"
    #: Something is left in this step.
    OPEN = "OPEN"
    #: Nothing to do here yet: a step before it is open.
    WAITING = "WAITING"


class ReadinessFix(str, Enum):
    """What the user does about an item."""

    #: Nothing to do but wait: the account or the market is being read.
    WAIT = "WAIT"
    RETRY_CONNECTION = "RETRY_CONNECTION"
    #: Change a parameter: `target` is the verdict code the kind's editor
    #: turns into the field to bring forward.
    EDIT_FIELD = "EDIT_FIELD"
    #: Stop the bot that is still active: `target` is its id.
    STOP_OTHER_BOT = "STOP_OTHER_BOT"
    #: Ask the exchange again (`BOT-173`): its facts could not be read.
    REFRESH_EXCHANGE = "REFRESH_EXCHANGE"
    #: The reason says what to do, and it is not on this screen (a key's
    #: permission, a strategy that holds the symbol).
    NONE = "NONE"


@dataclass(frozen=True, slots=True)
class ReadinessItem:
    """One thing left before Start."""

    step: ReadinessStep
    #: A stable name a test or a screen can key on.
    code: str
    reason: str
    fix: ReadinessFix
    #: The refusal Start answers when this is the first item left.
    refusal: BotRefusal
    target: str = ""


@dataclass(frozen=True, slots=True)
class ReadinessAdvisory:
    """`BOT-173` — something the owner should know before Start that does not
    stand in its way (the kind's advice is never an item either)."""

    #: A stable name a test or a screen can key on.
    code: str
    text: str


@dataclass(frozen=True, slots=True)
class StepReadiness:
    step: ReadinessStep
    status: StepStatus
    items: tuple[ReadinessItem, ...] = ()


@dataclass(frozen=True, slots=True)
class BotReadiness:
    steps: tuple[StepReadiness, ...]
    #: What the exchange's facts say that does not block Start (`BOT-173`).
    advisories: tuple[ReadinessAdvisory, ...] = ()

    @property
    def items(self) -> tuple[ReadinessItem, ...]:
        return tuple(item for step in self.steps for item in step.items)

    @property
    def things_left(self) -> int:
        return len(self.items)

    @property
    def can_start(self) -> bool:
        return not self.items

    def step(self, step: ReadinessStep) -> StepReadiness:
        return next(s for s in self.steps if s.step is step)

    @property
    def summary(self) -> str:
        """What the primary action's label and the progress header say."""
        left = self.things_left
        if left == 0:
            return "Ready to start"
        return f"{left} thing{'' if left == 1 else 's'} left"

    def message(self) -> str:
        """Every item's reason on one line: what Start answers when it
        refuses, in the words the screen showed before the click."""
        return f"{self.summary}: " + "; ".join(item.reason for item in self.items)
