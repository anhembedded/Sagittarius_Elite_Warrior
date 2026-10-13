"""`EPIC-029B` — "resume this bot". Continue a PAUSED bot, or re-plan a HALTED one (ADR D13)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ResumeBotCommand:
    """The bot to resume. A HALTED bot's resume reopens the venue's order session, so
    on a mainnet venue it carries the user's answer to the real-money question
    (`BUG-202`, as Start does: `EPIC-035V`)."""

    bot_id: str
    real_money_confirmed: bool = False
