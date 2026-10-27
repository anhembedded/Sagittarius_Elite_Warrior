"""`BOT-171`, `EPIC-048B` — one venue a bot may be on, and what is known of its connection.

@details The vocabulary of the venue pickers (New bot and the Plan's Venue field), held in
`contracts/` because it is a value both the host's answer (`GetVenueChoicesQuery`) and the
screen's widgets hold, and it crosses the remote link as the answer's content. The connection
is words, never a key: whether the venue has a saved API key and nothing of it.
"""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

KEY_SAVED = "API key saved"
NO_KEY = "no API key"
NOT_ENABLED = "not enabled"


@dataclass(frozen=True, slots=True)
class VenueChoice:
    """One venue a bot may be on, and what is known of its connection."""

    venue: TradingVenue
    connection: str
    #: Why no bot may be created on this venue yet; `None` when one may.
    closed_reason: str | None = None

    @property
    def option_text(self) -> str:
        return f"{self.venue.display_name} — {self.connection}"


@dataclass(frozen=True, slots=True)
class VenueChoices:
    """The venues a bot may be on: those with an API key first, then in `TradingVenue`
    order, the closed ones last (`BUG-155`)."""

    choices: tuple[VenueChoice, ...] = ()
