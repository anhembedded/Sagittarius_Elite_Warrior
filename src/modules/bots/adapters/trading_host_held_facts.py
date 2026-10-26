"""`EPIC-047B` — the host's facts, read from the ports the Bots screen's own reads use (decision G7a).

@details One look is local and builds nothing: the enabled venues and the lease holders come from
`IVenueTradingPorts` (the reads `BotRunFactsReader` makes), the caps are the owner's budget caps it
is given, the key state is `IExchangeCredentialsProvider.resolve()` as the Plan's venue choices read
it, and the snapshots are the readiness reads already taken (`ILatestVenueReads`). It never asks the
exchange and never reads a venue nothing has built: `IVenueContexts.get` builds a venue's adapters,
so a venue is read only when `IVenueContexts.built()` says something asked for it already.

A lease is read for each symbol a stored bot is on, on each built venue: the Run step asks it for a
venue and symbol the screen shows, which may be a draft's.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_held_facts import (
    HostHeldFacts,
    SymbolLease,
    VenueKeyState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_host_held_facts import (
    IHostHeldFacts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_latest_venue_reads import (
    ILatestVenueReads,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerBudgetCaps,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class TradingHostHeldFacts(IHostHeldFacts):
    def __init__(
        self,
        ports: IVenueTradingPorts,
        contexts: IVenueContexts,
        store: IBotStore,
        caps: OwnerBudgetCaps,
        reads: ILatestVenueReads,
    ) -> None:
        self._ports = ports
        self._contexts = contexts
        self._store = store
        self._caps = caps
        self._reads = reads

    def read(self) -> HostHeldFacts:
        enabled = self._ports.enabled()
        built = tuple(venue for venue in enabled if venue in self._contexts.built())
        stored = self._store.load_all().bots
        symbols = sorted({item.bot.definition.symbol for item in stored})
        known = {item.bot.bot_id.value for item in stored}
        return HostHeldFacts(
            enabled_venues=enabled,
            venue_keys=tuple(
                VenueKeyState(venue, self._key_saved(venue)) for venue in built
            ),
            leases=tuple(
                SymbolLease(venue, symbol, self._holder(venue, symbol))
                for venue in built
                for symbol in symbols
            ),
            caps=self._caps,
            exchange_reads=tuple(
                read for read in self._reads.latest() if read.bot_id in known
            ),
        )

    def _key_saved(self, venue: TradingVenue) -> bool:
        resolved = self._contexts.get(venue).credentials_provider.resolve()
        return resolved.credentials is not None

    def _holder(self, venue: TradingVenue, symbol: str) -> str:
        return self._ports.get(venue).trading_session.lease_holder(symbol) or ""
