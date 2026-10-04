"""`EPIC-029E` — "lay the ladder this HALTED bot's resume proposed" (ADR D13, O2)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ConfirmBotResumeCommand:
    bot_id: str
