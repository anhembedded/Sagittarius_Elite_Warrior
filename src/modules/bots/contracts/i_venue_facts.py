"""`EPIC-039E` — port: what a venue says about a bot's symbol and account, whichever the market.

@details Generalises `ExchangeFactsReader` (`BOT-174`). Spot's adapter answers today's
`ExchangeSnapshot` unchanged; Futures' answers a `FuturesSnapshot`. A caller that knows its
venue is Spot reads the narrower type through the Spot adapter; one that does not asks this
port and hands the snapshot to `judge_venue`, which picks the rules by the venue's profile.
Never raises: a failed read is `ExchangeUnavailable` with the reason.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.futures_facts import (
    VenueSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import Bot


class IVenueFacts(ABC):
    @abstractmethod
    def read(self, bot: Bot) -> VenueSnapshot:
        """The facts about `bot`'s symbol and account, now."""
