"""`EPIC-029B` — "start this bot" (from DRAFT or STOPPED)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StartBotCommand:
    """The bot to start."""

    bot_id: str
