"""`EPIC-029B` — "resume this bot". Continue a PAUSED bot, or re-plan a HALTED one (ADR D13)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ResumeBotCommand:
    """The bot to resume."""

    bot_id: str
