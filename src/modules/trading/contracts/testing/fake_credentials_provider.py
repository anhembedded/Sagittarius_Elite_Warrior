"""`IExchangeCredentialsProvider`'s fake: a venue's key is saved, or it is not.

@details For the tests of a screen that only asks whether a venue has a key
(`VenueChoice` on the Bots screen). It answers what the test says and stores
nothing: `save_to_file` makes the key exist, `remove_stored` forgets it, as the
real provider's file source does.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
    IExchangeCredentialsProvider,
    ResolvedCredentials,
)


class FakeCredentialsProvider(IExchangeCredentialsProvider):
    def __init__(self, *, has_key: bool = True) -> None:
        self._credentials = (
            ExchangeCredentials("fake-key", "fake-secret") if has_key else None
        )

    def resolve(self) -> ResolvedCredentials:
        if self._credentials is None:
            return ResolvedCredentials(None, CredentialsSource.NONE)
        return ResolvedCredentials(self._credentials, CredentialsSource.FILE)

    def save_to_file(self, api_key: str, api_secret: str) -> None:
        self._credentials = ExchangeCredentials(api_key, api_secret)

    def remove_stored(self) -> None:
        self._credentials = None
