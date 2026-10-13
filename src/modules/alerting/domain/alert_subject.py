"""What an alert is about: a bot, a venue, or the whole app."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SubjectScope(Enum):
    BOT = "bot"
    VENUE = "venue"
    APP = "app"


@dataclass(frozen=True, slots=True)
class AlertSubject:
    """Built through `bot`, `venue_wide` or `app`, so a subject is valid on
    creation. A bot subject carries what a future "Stop this bot" action needs
    to point at the right bot.

    `venue` is a label (`"spot-mainnet"`), not a Binance type: the module reads
    other modules' events through their contracts and names no venue class.
    """

    scope: SubjectScope
    bot_id: str = ""
    bot_name: str = ""
    bot_kind: str = ""
    venue: str = ""
    symbol: str = ""

    def __post_init__(self) -> None:
        if self.scope is SubjectScope.BOT and not self.bot_id:
            raise ValueError("A bot subject needs a bot id")
        if self.scope is SubjectScope.VENUE and not self.venue:
            raise ValueError("A venue subject needs a venue")

    @classmethod
    def bot(
        cls, bot_id: str, name: str, kind: str, venue: str, symbol: str
    ) -> AlertSubject:
        return cls(SubjectScope.BOT, bot_id, name, kind, venue, symbol)

    @classmethod
    def venue_wide(cls, venue: str) -> AlertSubject:
        return cls(SubjectScope.VENUE, venue=venue)

    @classmethod
    def app(cls) -> AlertSubject:
        return cls(SubjectScope.APP)

    @property
    def identity(self) -> str:
        """A stable text for dedup keys: who this is, not how it is named."""
        if self.scope is SubjectScope.BOT:
            return f"bot={self.bot_id}"
        if self.scope is SubjectScope.VENUE:
            return f"venue={self.venue}"
        return "app"
