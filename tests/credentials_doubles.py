"""An `IExchangeCredentialsProvider` for tests that only resolve a key.

@details Most tests need a provider that answers `resolve()` and is never asked to
store or remove anything. Subclass this, define `resolve()`, and a port gaining a
method changes this file instead of every test's own double (`BUG-176` added
`remove_stored()` to 30 of them).
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    IExchangeCredentialsProvider,
)


class ResolveOnlyCredentials(IExchangeCredentialsProvider):
    def save_to_file(self, api_key: str, api_secret: str) -> None:
        raise AssertionError("not used by this test")

    def remove_stored(self) -> None:
        raise AssertionError("not used by this test")
