"""`EPIC-034D` — `IVenueAccounts`, one reader per served account source.

@details The testnet sources are the venues `IVenueContexts` enables, each
read through the same ports its desk uses. Which venues exist is
`IVenueContexts`'s answer; this registry keeps no second copy, only the
readers it has built. The read-only mainnet source (`EPIC-034E`) is always
served, last: it has no venue and no desk, and without a key its reader says so
(`NOT_CONFIGURED`) instead of the source being absent.
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
    def __init__(
        self, contexts: IVenueContexts, mainnet_read_only: IVenueAccountReader
    ) -> None:
        self._contexts = contexts
        self._mainnet = mainnet_read_only
        self._readers: dict[AccountSource, IVenueAccountReader] = {}
        self._lock = threading.Lock()

    def sources(self) -> tuple[AccountSource, ...]:
        testnets = tuple(AccountSource.for_venue(v) for v in self._contexts.enabled())
        return (*testnets, self._mainnet.source)

    def reader(self, source: AccountSource) -> IVenueAccountReader:
        if source not in self.sources():
            raise UnknownAccountSourceError(source)
        if source is self._mainnet.source:
            return self._mainnet
        with self._lock:
            reader = self._readers.get(source)
            if reader is None:
                venue = source.trading_venue
                if venue is None:
                    raise UnknownAccountSourceError(source)
                reader = ComposedVenueAccountReader(source, self._contexts.get(venue))
                self._readers[source] = reader
            return reader
