"""`EPIC-047B` — the facts only a running host holds in memory, as one value.

@details A second process (the bridge, `EPIC-047C`) reads the store's files but can reach nothing
the running host keeps in memory: which venues are enabled and built, whether each has a key,
who holds a symbol's lease, the owner's budget caps and what the exchange last answered about a
bot. The host publishes them as this value (`IHostHeldFacts`) and the operations module writes
it to a file. It names no secret: a venue's key is *saved or not*, a lease is a symbol and its
holder's id, an exchange answer is the snapshot the readiness reader already built, with every
free-text reason replaced when the file is encoded (`UNAVAILABLE_WORDS`), because an exchange
failure's own words may carry what a key or a URL carried.

@par Why these four groups
They are what the Bots screen reads for a bot besides the store: `BotRunFactsReader` (enabled
venues, leases, caps), the Plan's venue choices (key saved) and `GetExchangeFactsQuery` (the
snapshot). Nothing here is a second source of any of them: the adapter reads the same ports.

@par Extension cases
  · a fifth group (the user stream's state, say) - one field with a default here and one read in
    `TradingHostHeldFacts`; the file's reader is unaffected until it asks for the field;
  · a lease on a symbol no bot is on (the Trade tab's) - `leases` lists the symbols of the stored
    bots only, since `ITradingSession` has no enumeration; one would add one.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.exchange_facts import (
    ExchangeUnavailable,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.futures_facts import (
    VenueSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.earlier_runs_inventory import (
    EarlierRunsInventory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerBudgetCaps,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

#: The free-text fields of a snapshot that an exchange failure fills, by type: an exception's words
#: may carry a key or a URL, so the file never writes them (the encoder says so in their place).
#: Declared here, beside the types, so the module that knows them is the one that lists them.
UNPUBLISHED_TEXT_FIELDS: dict[type, str] = {
    ExchangeUnavailable: "reason",
    EarlierRunsInventory: "unavailable",
}


@dataclass(frozen=True, slots=True)
class VenueKeyState:
    """Whether a built venue has an API key saved. Never the key."""

    venue: TradingVenue
    key_saved: bool


@dataclass(frozen=True, slots=True)
class SymbolLease:
    """Who holds `symbol`'s lease on `venue`: an owner's id, or `""` when nobody does."""

    venue: TradingVenue
    symbol: str
    holder: str


@dataclass(frozen=True, slots=True)
class BotExchangeRead:
    """The last snapshot the host's own readers took for a bot (`ExchangeFacts.read_at` or
    `FuturesFacts.read_at` says when). Recorded, never fetched for the file."""

    bot_id: str
    snapshot: VenueSnapshot


@dataclass(frozen=True, slots=True)
class HostHeldFacts:
    """Everything only the host holds, at one moment. Equality is the change test: two reads
    that are equal are one fact."""

    #: The enabled venues, in configuration order.
    enabled_venues: tuple[TradingVenue, ...]
    #: Key state of every enabled venue, built or not (`IVenueKeyStates` reads the stored key alone).
    venue_keys: tuple[VenueKeyState, ...]
    #: One entry per enabled venue and per symbol a stored bot is on; a venue nothing has built has
    #: no session to hold a lease, so its holder is `""`.
    leases: tuple[SymbolLease, ...]
    caps: OwnerBudgetCaps
    exchange_reads: tuple[BotExchangeRead, ...] = field(default=())
