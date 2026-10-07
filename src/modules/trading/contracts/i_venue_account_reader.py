"""`EPIC-034D` — reads one account and one symbol for the Connect step.

@details One implementation per source: the testnet venues compose their
existing readers (`ComposedVenueAccountReader`), and `EPIC-034E`'s read-only
mainnet source implements this port and nothing else, so it has no trading
port to confuse it with. The port can only read: nothing here places, tests
or cancels an order.

Plausible extensions, each one implementation behind this port: a caching
decorator keyed by `(source, symbol)`; a Futures mainnet read-only source.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connect_failure import (
    ConnectFailure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_account_snapshot import (
    VenueAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.account_source import (
    AccountSource,
)


class IVenueAccountReader(ABC):
    """One account source, read for one symbol at a time."""

    @property
    @abstractmethod
    def source(self) -> AccountSource: ...

    @abstractmethod
    def read(self, symbol: str) -> VenueAccountSnapshot | ConnectFailure:
        """@brief Reads the account, the venue's terms and `symbol`'s filters
        and price, all read-only.
        @return A snapshot, or the failure that stopped the read. Never
        raises: every outcome is a value."""
