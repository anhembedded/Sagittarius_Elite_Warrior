"""`EPIC-021B` — env-var first, gitignored file second, then none.
`EPIC-027G` — the env var pair is now looked up per `TradingVenue`, so
Futures Testnet and Spot Testnet keys can never be mixed up."""

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

#: `DISABLED` is deliberately absent — a disabled venue has no key set to
#: read; `resolve()` falls through to the (venue-agnostic) file fallback for
#: it, same as any venue whose env vars are unset (`EPIC-027G`).
_ENV_VAR_NAMES: dict[TradingVenue, tuple[str, str]] = {
    TradingVenue.FUTURES_TESTNET: (FUTURES_ENV_API_KEY, FUTURES_ENV_API_SECRET),
    TradingVenue.SPOT_TESTNET: (SPOT_ENV_API_KEY, SPOT_ENV_API_SECRET),
}


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
        env_var_names = _ENV_VAR_NAMES.get(self._trading_venue)
        api_key = os.environ.get(env_var_names[0]) if env_var_names else None
        api_secret = os.environ.get(env_var_names[1]) if env_var_names else None
        if api_key and api_secret:
            return ResolvedCredentials(
                ExchangeCredentials(api_key, api_secret), CredentialsSource.ENV
            )

        from_file = self._secrets_file.read()
        if from_file is not None:
            file_key, file_secret = from_file
            return ResolvedCredentials(
                ExchangeCredentials(file_key, file_secret), CredentialsSource.FILE
            )

        return ResolvedCredentials(None, CredentialsSource.NONE)

    def save_to_file(self, api_key: str, api_secret: str) -> None:
        self._secrets_file.write(api_key, api_secret)
