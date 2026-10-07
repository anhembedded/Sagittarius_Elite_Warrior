"""`BUG-176` — three fake Binance exchanges at once, for the key enrolment journeys.

@details Mainnet, Spot Testnet and Futures Testnet, each knowing a different set of
keys, with python-binance's four hosts pointed at them, and each venue's real
credentials provider (a temp `secrets.local.json` for the testnets, an in-memory store
standing in for the keyring for the mainnets).
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

from binance.client import Client
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.key_environment_probe import (
    BinanceKeyEnvironmentProbe,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.credentials.enrol_key import (
    EnrolKeyCommand,
    EnrolKeyCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.key_enrolment import (
    KeyEnrolment,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_contexts import (
    FakeVenueContexts,
    fake_venue_context,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.adapters.env_first_credentials_provider import (
    EnvFirstCredentialsProvider,
    MainnetCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.adapters.secrets_file_source import (
    SecretsFileSource,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    IExchangeCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.secret_stores import (
    InMemorySecretStore,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "tests" / "sanity"))
from binance_fake_server import run_binance_fake_server
from fake_exchange.server import FakeServerUrls

PLACING = ("POST", "PUT", "DELETE")
KEY = "k" * 64
SECRET = "s" * 64
OLD_FUTURES_TESTNET_KEY = "f" * 64
OLD_SPOT_MAINNET_KEY = "o" * 64
FUTURES_TESTNET = TradingVenue.FUTURES_TESTNET
SPOT_TESTNET = TradingVenue.SPOT_TESTNET
FUTURES_MAINNET = TradingVenue.FUTURES_MAINNET
SPOT_MAINNET = TradingVenue.SPOT_MAINNET


@dataclass
class World:
    mainnet: FakeServerUrls
    spot_testnet: FakeServerUrls
    futures_testnet: FakeServerUrls
    providers: dict[TradingVenue, IExchangeCredentialsProvider]
    keyring: InMemorySecretStore
    secrets_file: Path

    def enrol(
        self, key: str = KEY, only_for: TradingVenue | None = None
    ) -> KeyEnrolment:
        handler = EnrolKeyCommandHandler(
            BinanceKeyEnvironmentProbe(), FakeVenueContexts(*self._contexts())
        )
        return handler.execute(
            EnrolKeyCommand(ExchangeCredentials(key, SECRET), only_for)
        )

    def _contexts(self):
        return [
            fake_venue_context(venue, credentials_provider=provider)
            for venue, provider in self.providers.items()
        ]

    def key_of(self, venue: TradingVenue) -> str | None:
        credentials = self.providers[venue].resolve().credentials
        return credentials.api_key if credentials else None

    def servers(self) -> tuple[FakeServerUrls, ...]:
        return (self.mainnet, self.spot_testnet, self.futures_testnet)


def build_world(tmp_path: Path, keyring: InMemorySecretStore) -> Iterator[World]:
    secrets_file = tmp_path / "secrets.local.json"
    with ExitStack() as stack:
        mainnet = stack.enter_context(run_binance_fake_server())
        spot_testnet = stack.enter_context(run_binance_fake_server())
        futures_testnet = stack.enter_context(run_binance_fake_server())
        for attribute, value in (
            ("API_URL", mainnet.spot),
            ("MARGIN_API_URL", mainnet.margin),
            ("API_TESTNET_URL", spot_testnet.spot),
            ("FUTURES_TESTNET_URL", futures_testnet.futures),
        ):
            stack.enter_context(patch.object(Client, attribute, value))
        file_source = SecretsFileSource(str(secrets_file))
        providers: dict[TradingVenue, IExchangeCredentialsProvider] = {
            FUTURES_TESTNET: EnvFirstCredentialsProvider(file_source, FUTURES_TESTNET),
            SPOT_TESTNET: EnvFirstCredentialsProvider(file_source, SPOT_TESTNET),
            FUTURES_MAINNET: MainnetCredentialsProvider(keyring, FUTURES_MAINNET),
            SPOT_MAINNET: MainnetCredentialsProvider(keyring, SPOT_MAINNET),
        }
        yield World(
            mainnet, spot_testnet, futures_testnet, providers, keyring, secrets_file
        )
