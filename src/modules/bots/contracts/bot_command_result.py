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
    #: A bot that ran (or runs) keeps its venue; so does a Futures bot.
    VENUE_FIXED = "VENUE_FIXED"
    #: ADR D20, `EPIC-029J` J1b: one bot at a time holds a symbol of a venue; another symbol and
    #: another venue are free.
    ONE_ACTIVE_BOT_PER_SYMBOL = "ONE_ACTIVE_BOT_PER_SYMBOL"
    #: ADR D20, `EPIC-029J` J1b: the venue already runs the most bots it runs together.
    VENUE_FULL = "VENUE_FULL"
    #: `EPIC-042E`, `EPIC-029J` J1b: a bot of the venue waits to recover, and starting another
    #: would open the session that resumes it.
    VENUE_RECOVERING = "VENUE_RECOVERING"
    #: `EPIC-029E` — start's preconditions (ADR §3.1): a Spot venue with
    #: trading on, no REFUSED verdict, the symbol's lease, the owner budget.
    VENUE_NOT_READY = "VENUE_NOT_READY"
    PARAMETERS_REFUSED = "PARAMETERS_REFUSED"
    #: `BOT-174` — the exchange's facts could not be read, so what they decide
    #: is not known; and an account that holds too little for the ladder.
    EXCHANGE_NOT_READ = "EXCHANGE_NOT_READ"
    BALANCE_TOO_SMALL = "BALANCE_TOO_SMALL"
    SYMBOL_LEASED = "SYMBOL_LEASED"
    BUDGET_REFUSED = "BUDGET_REFUSED"
    #: A HALTED bot's executor holds no resume proposal to confirm (none
    #: asked for since the halt, or the app restarted): Resume first.
    NO_RESUME_PROPOSAL = "NO_RESUME_PROPOSAL"
    #: `EPIC-045G` (owner decision O3) - a confirmation named a proposal that is not the held one: a
    #: later resume re-proposed, so what the person read is not what would be laid.
    RESUME_PROPOSAL_CHANGED = "RESUME_PROPOSAL_CHANGED"
    #: `EPIC-035H` — another copy of the app holds the data root; this one
    #: reads bots and starts none.
    READ_ONLY_INSTANCE = "READ_ONLY_INSTANCE"
    #: `EPIC-035V` — a bot on a mainnet venue was started by a caller that did
    #: not carry the user's answer to the real-money question.
    REAL_MONEY_NOT_CONFIRMED = "REAL_MONEY_NOT_CONFIRMED"
    #: `EPIC-039H` (decision O8) — a Stop that would keep a position on a position venue:
    #: no exchange-side stop stands, so the bot closes it.
    EXPOSURE_MUST_CLOSE = "EXPOSURE_MUST_CLOSE"
    #: `EPIC-045B` — `bot delete` on the running host: the bot's record still shows a held base, a
    #: live order or an order it owes, so forgetting it would orphan them.
    EXPOSURE_LEFT = "EXPOSURE_LEFT"
    #: `EPIC-026L` — the account-level loss cap is tripped: no bot starts or resumes until the
    #: owner acknowledges it.
    LOSS_CAP_TRIPPED = "LOSS_CAP_TRIPPED"
    #: `EPIC-026L` — an acknowledgement of a cap that is not tripped.
    LOSS_CAP_NOT_TRIPPED = "LOSS_CAP_NOT_TRIPPED"
    #: `EPIC-026L` — an acknowledgement while the day's loss is still at or above the figure.
    LOSS_CAP_STILL_AT_FIGURE = "LOSS_CAP_STILL_AT_FIGURE"


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
