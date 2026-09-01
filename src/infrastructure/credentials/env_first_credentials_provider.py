"""`EPIC-021B` — env-var first, gitignored file second, then none."""

from __future__ import annotations

import os

from Sagittarius_Elite_Warrior.src.application.ports.i_exchange_credentials_provider import (
    CredentialsSource,
    IExchangeCredentialsProvider,
    ResolvedCredentials,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.infrastructure.credentials.secrets_file_source import (
    SecretsFileSource,
)

#: Tied to the venue, not generic — Futures Testnet has its own key set, not
#: shared with Spot Testnet or mainnet (`EPIC-021B` §2.1). A generic
#: `BINANCE_API_KEY` name would invite the single most expensive mix-up this
#: epic exists to prevent.
ENV_API_KEY = "BINANCE_FUTURES_TESTNET_API_KEY"
ENV_API_SECRET = "BINANCE_FUTURES_TESTNET_API_SECRET"  # noqa: S105 - env var name, not a secret value


class EnvFirstCredentialsProvider(IExchangeCredentialsProvider):
    """@brief Environment variables win outright over the file fallback —
    the only way to run headless (CI/VPS) without ever putting a secret on
    disk, and a machine already configured correctly must never be
    silently overridden by a stale file (`EPIC-021B` §2.1)."""

    def __init__(self, secrets_file: SecretsFileSource) -> None:
        self._secrets_file = secrets_file

    def resolve(self) -> ResolvedCredentials:
        api_key = os.environ.get(ENV_API_KEY)
        api_secret = os.environ.get(ENV_API_SECRET)
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
