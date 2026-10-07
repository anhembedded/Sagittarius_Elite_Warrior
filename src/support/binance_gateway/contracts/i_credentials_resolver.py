"""`EPIC-034E` — resolving an API key pair, and nothing else.

@details `IExchangeCredentialsProvider` also writes a key to a file, which is
what a venue that trades needs (Settings saves its key). The read-only mainnet
account must never write its secret to disk (D10), so it implements this
narrower port and the file-writing one is not available to it: the wrong state
has no method to call (`code/errors.md` #8).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    ResolvedCredentials,
)


class ICredentialsResolver(ABC):
    @abstractmethod
    def resolve(self) -> ResolvedCredentials:
        """The credentials in priority order and which source produced them.
        Never raises: no credentials is `CredentialsSource.NONE`."""
