"""`EPIC-034D` — `IVenueAccounts`, one reader per served account source.

@details The testnet sources are the venues `IVenueContexts` enables, each
read through the same ports its desk uses. Which venues exist is
`IVenueContexts`'s answer; this registry keeps no second copy, only the
readers it has built.
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
                venue = source.trading_venue
                if venue is None:
                    raise UnknownAccountSourceError(source)
                reader = ComposedVenueAccountReader(source, self._contexts.get(venue))
                self._readers[source] = reader
            return reader
