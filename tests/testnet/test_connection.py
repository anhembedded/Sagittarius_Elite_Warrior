"""`EPIC-021J` §2.4/§5 — the first (and simplest) real-testnet check: the
app can actually reach the exchange with real credentials. Opt-in only —
see `conftest.py` for the two gates.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.application.ports.i_exchange_credentials_provider import (
    CredentialsSource,
    ResolvedCredentials,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.market_data_venue import (
    MarketDataVenue,
)
from Sagittarius_Elite_Warrior.src.infrastructure.binance.exchange_session_factory import (
    ExchangeSessionFactory,
)
from Sagittarius_Elite_Warrior.src.infrastructure.binance.futures_account_reader import (
    FuturesAccountReader,
)


class _StaticCredentialsProvider:
    def __init__(self, credentials: ExchangeCredentials) -> None:
        self._credentials = credentials

    def resolve(self) -> ResolvedCredentials:
        return ResolvedCredentials(self._credentials, CredentialsSource.ENV)

    def save_to_file(self, api_key: str, api_secret: str) -> None:
        raise NotImplementedError("not used by this tier")


def test_account_is_reachable(testnet_credentials: ExchangeCredentials) -> None:
    """Same call `main.py exchange-status` makes — real signed requests to
    Futures Testnet, no fake server anywhere in this tier."""
    session_factory = ExchangeSessionFactory(MarketDataVenue.FUTURES_TESTNET)
    reader = FuturesAccountReader(
        session_factory, _StaticCredentialsProvider(testnet_credentials)
    )

    status = reader.check_connection()

    assert status.reachable is True
    assert status.failure is None
    assert status.usdt_balance is not None
