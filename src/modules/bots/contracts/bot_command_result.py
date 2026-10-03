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
