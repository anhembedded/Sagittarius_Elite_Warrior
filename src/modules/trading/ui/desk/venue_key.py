"""`EPIC-034B` — a desk of a venue with no key reads nothing, and says why.

@details Every venue is assembled whatever the configuration says, so a desk is
built for a venue the person never gave a key. Its account reads cannot succeed:
each would raise inside the query dispatcher, which logs it at ERROR, and the
desk would greet every start with a screen of failures about a state that is
not one — a venue without a key is a known state, shown as one. A desk asks
`KeyCheck` before it reads the account and, with no key, says "No API key" in
the words below instead. The check reads the credentials provider on each call
(no network, no cache), so a key saved in Tools → Options → Trading is seen by
the next read, with no restart.
"""

from __future__ import annotations

from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.interfaces.i_container import IContainer

#: Whether the venue has a key the app can sign with, now.
type KeyCheck = Callable[[], bool]


def always_keyed() -> bool:
    """The check of a desk built over fakes: it has whatever the test gives it."""
    return True


def no_key_text(venue: TradingVenue) -> str:
    """What a desk says in place of an account it did not read."""
    title = venue.value.replace("_", " ").title()
    return f"No API key for {title} — save one in Tools → Options → Trading."


def venue_key_check(container: IContainer, venue: TradingVenue) -> KeyCheck:
    """`venue`'s check, over the credentials provider its readers resolve from."""
    provider = container.resolve(IVenueContexts).get(venue).credentials_provider
    return lambda: provider.resolve().credentials is not None
