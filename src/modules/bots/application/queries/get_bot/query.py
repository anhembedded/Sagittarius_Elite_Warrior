"""`EPIC-029B` — "this one bot, for its panel"."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GetBotQuery:
    """The bot to show."""

    bot_id: str
