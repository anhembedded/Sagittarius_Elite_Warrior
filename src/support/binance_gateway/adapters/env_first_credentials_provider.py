"""`EPIC-021B` — env-var first, gitignored file second, then none.
`EPIC-027G` — the env var pair is now looked up per `TradingVenue`, so
Futures Testnet and Spot Testnet keys can never be mixed up.
`EPIC-034` D11 — the mainnet venues have their own pairs and their own provider:
env first, then the operating system's keyring, never a file (D10)."""

from __future__ import annotations

import os

from Sagittarius_Elite_Warrior.src.support.binance_gateway.adapters.secrets_file_source import (
    SecretsFileSource,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
    IExchangeCredentialsProvider,
    ResolvedCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_secret_store import (
    ISecretStore,
    SecretStoreUnavailableError,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

#: Tied to the venue, not generic — Futures Testnet has its own key set, not
#: shared with Spot Testnet or mainnet (`EPIC-021B` §2.1). A generic
#: `BINANCE_API_KEY` name would invite the single most expensive mix-up this
#: epic exists to prevent.
FUTURES_ENV_API_KEY = "BINANCE_FUTURES_TESTNET_API_KEY"
FUTURES_ENV_API_SECRET = "BINANCE_FUTURES_TESTNET_API_SECRET"  # noqa: S105 - env var name, not a secret value
SPOT_ENV_API_KEY = "BINANCE_SPOT_TESTNET_API_KEY"
SPOT_ENV_API_SECRET = "BINANCE_SPOT_TESTNET_API_SECRET"  # noqa: S105 - env var name, not a secret value
#: `EPIC-034` D11 — a mainnet key is never read as a testnet key, nor the reverse:
#: each of the four venues has a pair of its own.
FUTURES_MAINNET_ENV_API_KEY = "BINANCE_FUTURES_MAINNET_API_KEY"
FUTURES_MAINNET_ENV_API_SECRET = "BINANCE_FUTURES_MAINNET_API_SECRET"  # noqa: S105 - env var name, not a secret value
SPOT_MAINNET_ENV_API_KEY = "BINANCE_SPOT_MAINNET_API_KEY"
SPOT_MAINNET_ENV_API_SECRET = "BINANCE_SPOT_MAINNET_API_SECRET"  # noqa: S105 - env var name, not a secret value

#: `DISABLED` is deliberately absent — a disabled venue has no key set to
#: read; `resolve()` falls through to the (venue-agnostic) file fallback for
#: it, same as any venue whose env vars are unset (`EPIC-027G`).
_ENV_VAR_NAMES: dict[TradingVenue, tuple[str, str]] = {
    TradingVenue.FUTURES_TESTNET: (FUTURES_ENV_API_KEY, FUTURES_ENV_API_SECRET),
    TradingVenue.SPOT_TESTNET: (SPOT_ENV_API_KEY, SPOT_ENV_API_SECRET),
    TradingVenue.FUTURES_MAINNET: (
        FUTURES_MAINNET_ENV_API_KEY,
        FUTURES_MAINNET_ENV_API_SECRET,
    ),
    TradingVenue.SPOT_MAINNET: (SPOT_MAINNET_ENV_API_KEY, SPOT_MAINNET_ENV_API_SECRET),
}


def _stripped_env(name: str) -> str | None:
    """`BUG-137` — a shell-pasted or `.env`-sourced value routinely carries
    a stray trailing newline or space; left in, it corrupts the signed
    request's `X-MBX-APIKEY` header and surfaces as an opaque `NETWORK`
    failure instead of naming the credentials problem. Stripped here, once,
    so every venue and every caller of `resolve()` gets the same immunity.
    A whitespace-only value strips to `""`, which is falsy — `resolve()`'s
    `if api_key and api_secret` already treats that as "not set" and falls
    through to the file source, same as a truly missing var."""
    value = os.environ.get(name)
    return value.strip() if value is not None else None


def _env_credentials(venue: TradingVenue) -> ExchangeCredentials | None:
    names = _ENV_VAR_NAMES.get(venue)
    api_key = _stripped_env(names[0]) if names else None
    api_secret = _stripped_env(names[1]) if names else None
    return ExchangeCredentials(api_key, api_secret) if api_key and api_secret else None


class EnvFirstCredentialsProvider(IExchangeCredentialsProvider):
    """@brief Environment variables win outright over the file fallback —
    the only way to run headless (CI/VPS) without ever putting a secret on
    disk, and a machine already configured correctly must never be
    silently overridden by a stale file (`EPIC-021B` §2.1).

    @details Bound to one `TradingVenue` for its lifetime (`EPIC-027G`) —
    the venue picks which env var pair `resolve()` reads, so a Futures
    Testnet key can never be read while Spot Testnet is active, or vice
    versa.
    """

    def __init__(
        self, secrets_file: SecretsFileSource, trading_venue: TradingVenue
    ) -> None:
        self._secrets_file = secrets_file
        self._trading_venue = trading_venue

    def resolve(self) -> ResolvedCredentials:
        from_env = _env_credentials(self._trading_venue)
        if from_env is not None:
            return ResolvedCredentials(from_env, CredentialsSource.ENV)

        from_file = self._secrets_file.read(self._trading_venue)
        if from_file is not None:
            file_key, file_secret = from_file
            return ResolvedCredentials(
                ExchangeCredentials(file_key, file_secret), CredentialsSource.FILE
            )

        return ResolvedCredentials(None, CredentialsSource.NONE)

    def save_to_file(self, api_key: str, api_secret: str) -> None:
        self._secrets_file.write(self._trading_venue, api_key, api_secret)

    def remove_stored(self) -> None:
        self._secrets_file.remove(self._trading_venue)


class MainnetCredentialsProvider(IExchangeCredentialsProvider):
    """@brief A mainnet venue's key: the environment first, then the operating
    system's keyring, and no file (`EPIC-034` D10, D11).

    @details Its own class rather than a flag on `EnvFirstCredentialsProvider`:
    that one falls back to `secrets.local.json`, and a real-money secret must
    never reach a file, so the wrong state has no code path (`code/errors.md` #8).
    Two names per venue in the store, `<venue>_api_key` and `<venue>_api_secret`,
    so a Spot key is never read for Futures. The store is read once and kept:
    the keyring can be a round trip to the desktop's secret service and this is
    asked every few seconds by the refresh services; a key saved while the app
    runs through `save_to_file` is picked up at once, one saved by the
    enrolment script at the next start.

    `save_to_file` keeps the port's name, which predates mainnet; for a mainnet
    venue the durable store it writes to is the keyring, never a file.
    """

    def __init__(self, store: ISecretStore, trading_venue: TradingVenue) -> None:
        self._store = store
        self._venue = trading_venue
        self._key_name = f"{trading_venue.value}_api_key"
        self._secret_name = f"{trading_venue.value}_api_secret"
        self._stored: ExchangeCredentials | None = None
        self._stored_read = False

    def resolve(self) -> ResolvedCredentials:
        from_env = _env_credentials(self._venue)
        if from_env is not None:
            return ResolvedCredentials(from_env, CredentialsSource.ENV)
        stored = self._stored_pair()
        if stored is not None:
            return ResolvedCredentials(stored, CredentialsSource.KEYRING)
        return ResolvedCredentials(None, CredentialsSource.NONE)

    def save_to_file(self, api_key: str, api_secret: str) -> None:
        """@raise SecretStoreUnavailableError The keyring cannot be used here."""
        previous = (
            self._store.read(self._key_name),
            self._store.read(self._secret_name),
        )
        try:
            self._store.write(self._key_name, api_key)
            self._store.write(self._secret_name, api_secret)
        except SecretStoreUnavailableError:
            # Never leave half a pair: put back what was there, or nothing.
            for name, before in zip(
                (self._key_name, self._secret_name), previous, strict=True
            ):
                if before is None:
                    self._store.delete(name)
                else:
                    self._store.write(name, before)
            self._stored = None
            self._stored_read = False
            raise
        self._stored = ExchangeCredentials(api_key, api_secret)
        self._stored_read = True

    def remove_stored(self) -> None:
        """@raise SecretStoreUnavailableError The keyring cannot be used here."""
        self._store.delete(self._key_name)
        self._store.delete(self._secret_name)
        self._stored = None
        self._stored_read = True

    def _stored_pair(self) -> ExchangeCredentials | None:
        if not self._stored_read:
            key = self._store.read(self._key_name)
            secret = self._store.read(self._secret_name)
            self._stored = ExchangeCredentials(key, secret) if key and secret else None
            self._stored_read = True
        return self._stored
