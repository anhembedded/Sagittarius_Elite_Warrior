"""`EPIC-039J` — "what does the venue say that this bot's plan can be liquidated by"."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GetPlanRiskFactsQuery:
    """The bot whose venue is asked; the venue and symbol are the bot's own."""

    bot_id: str
