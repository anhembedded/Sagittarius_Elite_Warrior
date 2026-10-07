"""`EPIC-034D` — `IVenueAccounts`, one reader per served account source.

@details A source is a venue `IVenueContexts` enables, read through the same ports
its desk uses; which venues exist is `IVenueContexts`'s answer and this registry
keeps no second copy, only the readers it has built. Every reader is a
`ComposedVenueAccountReader`; a mainnet venue's has the key gate in front
(`EPIC-034` D5, D11), the one thing it does that a testnet venue's does not.
"""

from __future__ import annotations

import threading

from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.mainnet.api_restrictions_key_gate import (
    ApiRestrictionsKeyGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.account.composed_venue_account_reader import (
    ComposedVenueAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_key_permission_gate import (
    IKeyPermissionGate,
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
        venue = source.trading_venue
        context = self._contexts.get(venue)
        gate: IKeyPermissionGate | None = (
            ApiRestrictionsKeyGate(
                venue, lambda: context.credentials_provider.resolve().credentials
            )
            if venue.is_mainnet
            else None
        )
        return ComposedVenueAccountReader(source, context, key_gate=gate)
