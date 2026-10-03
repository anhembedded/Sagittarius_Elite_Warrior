"""`EPIC-029B` — "delete this bot" (DRAFT or STOPPED only)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DeleteBotCommand:
    """The bot to forget."""

    bot_id: str
