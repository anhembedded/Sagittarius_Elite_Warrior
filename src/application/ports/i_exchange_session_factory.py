"""Application port for building a ready-to-use market-data exchange client
against the app's configured `MarketDataVenue` (`EPIC-021A`)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.application.ports.i_exchange_client import (
    IExchangeClient,
)


class IExchangeSessionFactory(ABC):
    """Port for the one place in the app allowed to construct a real
    `python-binance` session. Only covers market-data for now — a trading
    session is `EPIC-021E`/`021F`'s concern, once `ITradingClient` exists as
    an Application-safe return type; this port must not name
    `binance.client.Client` in its own signature (`architecture-rule.md` §3)."""

    @abstractmethod
    def create_market_data_client(self) -> IExchangeClient:
        """Builds an `IExchangeClient` wired to this factory's configured
        `MarketDataVenue` — no key for `MAINNET_PUBLIC`, `testnet=True` and
        the matching `klines_type` for `FUTURES_TESTNET`."""
