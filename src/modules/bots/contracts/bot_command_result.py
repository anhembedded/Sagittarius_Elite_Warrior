"""`EPIC-029B` — what every bot command answers.

A refusal is a value, like every other refusal in this application (the symbol
lease answers a `bool`, arming answers a block reason): the screen shows the
reason, and nothing about the bot changed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class BotRefusal(str, Enum):
    """Why a bot command changed nothing."""

    NOT_FOUND = "NOT_FOUND"
    UNREADABLE = "UNREADABLE"
    INVALID_TRANSITION = "INVALID_TRANSITION"
    INVALID_DEFINITION = "INVALID_DEFINITION"
    #: ADR D20: during the fast track one bot at a time holds the exchange.
    ONE_RUNNING_BOT_DURING_FAST_TRACK = "ONE_RUNNING_BOT_DURING_FAST_TRACK"
    #: `EPIC-029E` — start's preconditions (ADR §3.1): a Spot venue with
    #: trading on, no REFUSED verdict, the symbol's lease, the owner budget.
    VENUE_NOT_READY = "VENUE_NOT_READY"
    PARAMETERS_REFUSED = "PARAMETERS_REFUSED"
    SYMBOL_LEASED = "SYMBOL_LEASED"
    BUDGET_REFUSED = "BUDGET_REFUSED"
    #: A HALTED bot's executor holds no resume proposal to confirm (none
    #: asked for since the halt, or the app restarted): Resume first.
    NO_RESUME_PROPOSAL = "NO_RESUME_PROPOSAL"


@dataclass(frozen=True, slots=True)
class BotCommandResult:
    """`accepted`, or the refusal and a sentence naming it."""

    accepted: bool
    bot_id: str | None = None
    refusal: BotRefusal | None = None
    message: str = ""

    @classmethod
    def done(cls, bot_id: str) -> BotCommandResult:
        return cls(accepted=True, bot_id=bot_id)

    @classmethod
    def refused(
        cls, refusal: BotRefusal, message: str, bot_id: str | None = None
    ) -> BotCommandResult:
        return cls(accepted=False, bot_id=bot_id, refusal=refusal, message=message)
