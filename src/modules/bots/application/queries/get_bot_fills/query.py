"""`EPIC-029F` — "what has this bot's run filled at the exchange"."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GetBotFillsQuery:
    bot_id: str
