"""`EPIC-034D` — how a screen reaches an account source's reader."""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_account_reader import (
    IVenueAccountReader,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.account_source import (
    AccountSource,
)


class UnknownAccountSourceError(LookupError):
    """A caller asked for a source this build does not serve: a wiring bug,
    never a condition to fall back from silently (`code/errors.md` #6)."""

    def __init__(self, source: AccountSource) -> None:
        super().__init__(f"Account source {source.value!r} is not served.")
        self.source = source


class IVenueAccounts(ABC):
    """Registry of the served account sources' readers."""

    @abstractmethod
    def sources(self) -> tuple[AccountSource, ...]:
        """The served sources, in configuration order."""

    @abstractmethod
    def reader(self, source: AccountSource) -> IVenueAccountReader:
        """The reader of `source`, the same instance on every call.
        @raise UnknownAccountSourceError `source` is not served."""
