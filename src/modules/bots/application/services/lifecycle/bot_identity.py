"""`EPIC-045G` - the two rules `bot add` and `bot move` share: which venues a bot may be on, and what
makes two bots "the same bot" (the identity a plan uses: a name on a venue).

One home for both, so a closed venue or a changed identity rule cannot leave the two host verbs
disagreeing about what counts as a duplicate.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import (
    IBotStore,
    StoredBot,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


def venue_of(text: str) -> TradingVenue | str:
    """The venue named `text`, or the words saying which venues this build trades on."""
    for venue in TradingVenue:
        if venue is not TradingVenue.DISABLED and venue.value == text:
            return venue
    allowed = ", ".join(v.value for v in TradingVenue if v is not TradingVenue.DISABLED)
    return f"{text!r} is not a venue of this build; one of: {allowed}"


def bot_with_name_on(
    store: IBotStore, name: str, venue: TradingVenue
) -> StoredBot | None:
    """The stored bot that already has `name` on `venue`, if any."""
    for stored in store.load_all().bots:
        held = stored.bot.definition
        if held.name == name and held.venue is venue:
            return stored
    return None
