"""`EPIC-034D` — the verified fake for `IVenueAccounts`.

@details Serves exactly the readers it is given, in the order given, and
refuses any other source with `UnknownAccountSourceError`, as the real
registry does (`tests/unit/modules/trading/test_module_venue_accounts_binding.py`).
`FakeVenueAccountReader` answers what a test says, and counts its reads, so a
caller reading per candle shows up.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connect_failure import (
    ConnectFailure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_account_reader import (
    IVenueAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_accounts import (
    IVenueAccounts,
    UnknownAccountSourceError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_account_snapshot import (
    VenueAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.account_source import (
    AccountSource,
)


class FakeVenueAccountReader(IVenueAccountReader):
    def __init__(
        self, source: AccountSource, answer: VenueAccountSnapshot | ConnectFailure
    ) -> None:
        self._source = source
        self._answer = answer
        self.symbols_read: list[str] = []

    @property
    def source(self) -> AccountSource:
        return self._source

    def answer_with(self, answer: VenueAccountSnapshot | ConnectFailure) -> None:
        """Sets what the next read answers."""
        self._answer = answer

    def read(self, symbol: str) -> VenueAccountSnapshot | ConnectFailure:
        self.symbols_read.append(symbol)
        return self._answer


class FakeVenueAccounts(IVenueAccounts):
    def __init__(self, *readers: IVenueAccountReader) -> None:
        self._readers = {reader.source: reader for reader in readers}

    def sources(self) -> tuple[AccountSource, ...]:
        return tuple(self._readers)

    def reader(self, source: AccountSource) -> IVenueAccountReader:
        try:
            return self._readers[source]
        except KeyError:
            raise UnknownAccountSourceError(source) from None
