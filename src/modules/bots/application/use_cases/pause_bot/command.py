"""`EPIC-029B` — "pause this bot". Stop placing orders; fills are still recorded (RUNNING only)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PauseBotCommand:
    """The bot to pause."""

    bot_id: str
