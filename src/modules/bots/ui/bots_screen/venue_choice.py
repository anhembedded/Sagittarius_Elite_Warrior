"""`BOT-171` — the venues a bot may be on, each with its connection state.

@details New bot and the Plan's Venue field offer the same list: every venue a bot kind
runs on and the owner has opened (`is_offered`: Futures mainnet stays closed until
`EPIC-039L`), each in its market's words. A kind is offered a venue only when it declares the
venue's market (`IBotKind.supported_profiles`). The state is what is known without a network call: whether the venue has an
API key (`credentials_provider` is the stored key, ungated — it never reaches the
exchange). Whether the key *works* is the Connect step's read, made once a bot is
on the venue, and its failure is told once, in the message bar (`BUG-181`).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind import IBotKind
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    is_offered,
    market_of,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
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

    @property
    def option_text(self) -> str:
        return f"{self.venue.display_name} — {self.connection}"


def venue_choices(
    contexts: IVenueContexts, kinds: Iterable[IBotKind]
) -> tuple[VenueChoice, ...]:
    """Every offered venue some kind runs on, those with an API key first, then in
    `TradingVenue` order, so the preselected one is a venue a bot can start on whenever one
    has a key (`BUG-155`)."""
    enabled = contexts.enabled()
    markets = frozenset(
        market for kind in kinds for market in kind.supported_profiles()
    )
    choices = [
        VenueChoice(venue, _connection_of(contexts, venue, enabled))
        for venue in TradingVenue
        if is_offered(venue) and market_of(venue) in markets
    ]
    return tuple(sorted(choices, key=lambda choice: choice.connection != KEY_SAVED))


def _connection_of(
    contexts: IVenueContexts, venue: TradingVenue, enabled: tuple[TradingVenue, ...]
) -> str:
    if venue not in enabled:
        return NOT_ENABLED
    saved = contexts.get(venue).credentials_provider.resolve().credentials
    return KEY_SAVED if saved is not None else NO_KEY
