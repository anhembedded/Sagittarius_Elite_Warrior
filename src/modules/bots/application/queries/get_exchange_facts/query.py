"""`BOT-173` — "what does the exchange say about this bot's symbol and account"."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GetExchangeFactsQuery:
    """The bot whose venue is asked; the venue and symbol are the bot's own."""

    bot_id: str
