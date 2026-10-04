"""`EPIC-029G` — a bot chart's identity on the market stream."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId


def bot_stream_owner(bot_id: BotId) -> str:
    """@brief A bot chart's own owner on the market stream (`BOT-126`):
    `bot.<id>`, so it never replaces a desk's subscription, nor another
    bot's."""
    return f"bot.{bot_id}"
