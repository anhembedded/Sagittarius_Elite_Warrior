"""`EPIC-034D` — `IVenueAccounts`, one reader per served account source.

@details A source is a venue `IVenueContexts` enables, read through the same ports
its desk uses; which venues exist is `IVenueContexts`'s answer and this registry
keeps no second copy, only the readers it has built. Every reader is a
`ComposedVenueAccountReader`; a mainnet venue's has the venue's key gate in
front (`EPIC-034` D5, D11) to say why a key is refused. The gate also sits under
every adapter's credentials (`VenueAssembly.order_credentials`), so it is not
this reader alone that stops a key that can withdraw.
"""

from __future__ import annotations

import threading

from Sagittarius_Elite_Warrior.src.modules.trading.application.account.composed_venue_account_reader import (
    ComposedVenueAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_account_reader import (
    IVenueAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_accounts import (
    IVenueAccounts,
    UnknownAccountSourceError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.account_source import (
    AccountSource,
)


class VenueAccounts(IVenueAccounts):
    def __init__(self, contexts: IVenueContexts) -> None:
        self._contexts = contexts
        self._readers: dict[AccountSource, IVenueAccountReader] = {}
        self._lock = threading.Lock()

    def sources(self) -> tuple[AccountSource, ...]:
        return tuple(AccountSource.for_venue(v) for v in self._contexts.enabled())

    def reader(self, source: AccountSource) -> IVenueAccountReader:
        if source not in self.sources():
            raise UnknownAccountSourceError(source)
        with self._lock:
            reader = self._readers.get(source)
            if reader is None:
                reader = self._build(source)
                self._readers[source] = reader
            return reader

    def _build(self, source: AccountSource) -> IVenueAccountReader:
        context = self._contexts.get(source.trading_venue)
        return ComposedVenueAccountReader(source, context, key_gate=context.key_gate)
