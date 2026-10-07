"""`EPIC-034E` — the read-only mainnet key: the environment first, then the
operating system's keyring.

@details Its own names, never the testnet venues' and never a generic
`BINANCE_API_KEY`: a testnet key can never be read as a mainnet key, nor the
reverse (`EPIC-021B` §2.1 names this the most expensive mix-up). The
environment wins outright, as it does for the venues, so a headless machine
needs no keyring. The keyring holds the pair a person saved with
`scripts/save_mainnet_readonly_key.py` (D10); the secret is never written to
`secrets.local.json` — this class has no file source, and nothing here
writes one.
"""

from __future__ import annotations

import os

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_credentials_resolver import (
    ICredentialsResolver,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
    ResolvedCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_secret_store import (
    ISecretStore,
)

MAINNET_READONLY_ENV_API_KEY = "BINANCE_MAINNET_READONLY_API_KEY"
MAINNET_READONLY_ENV_API_SECRET = "BINANCE_MAINNET_READONLY_API_SECRET"  # noqa: S105 - env var name, not a secret value
#: The names the pair has in the secret store.
STORED_API_KEY = "mainnet_readonly_api_key"
STORED_API_SECRET = "mainnet_readonly_api_secret"  # noqa: S105 - entry name, not a secret value


def _stripped_env(name: str) -> str | None:
    """A pasted value carries a stray newline or space (`BUG-137`); a
    whitespace-only value is "not set"."""
    value = os.environ.get(name)
    return value.strip() if value is not None and value.strip() else None


class MainnetReadOnlyCredentials(ICredentialsResolver):
    def __init__(self, store: ISecretStore) -> None:
        self._store = store

    def resolve(self) -> ResolvedCredentials:
        api_key = _stripped_env(MAINNET_READONLY_ENV_API_KEY)
        api_secret = _stripped_env(MAINNET_READONLY_ENV_API_SECRET)
        if api_key and api_secret:
            return ResolvedCredentials(
                ExchangeCredentials(api_key, api_secret), CredentialsSource.ENV
            )
        stored_key = self._store.read(STORED_API_KEY)
        stored_secret = self._store.read(STORED_API_SECRET)
        if stored_key and stored_secret:
            return ResolvedCredentials(
                ExchangeCredentials(stored_key, stored_secret),
                CredentialsSource.KEYRING,
            )
        return ResolvedCredentials(None, CredentialsSource.NONE)

    def save(self, credentials: ExchangeCredentials) -> None:
        """Keeps the pair in the secret store, for later runs.
        @raise SecretStoreUnavailableError The store cannot be used."""
        self._store.write(STORED_API_KEY, credentials.api_key)
        self._store.write(STORED_API_SECRET, credentials.api_secret)
