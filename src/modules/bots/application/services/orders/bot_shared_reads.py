"""`BOT-184`, `BOT-221` — the shared readings one bot's idle watches take, and drops on an order.

A bot's gateway holds these; `BotAccountReads` serves the watches from them and drops them when
the bot sends or cancels an order or hears a fill. Each is optional: a bot without one reads the
account for itself, as before sharing.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.risk.bounded_age_reading import (
    BoundedAgeReading,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.risk.venue_position_reads import (
    VenuePositionReads,
)


@dataclass(frozen=True, slots=True)
class BotSharedReads:
    """The venue's positions reading and the bot's symbol's mark reading."""

    positions: VenuePositionReads | None = None
    mark: BoundedAgeReading[Decimal] | None = None
