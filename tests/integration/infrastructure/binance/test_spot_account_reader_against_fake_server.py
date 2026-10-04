"""`SpotAccountReader` over a real HTTP round trip to the fake exchange: the
Spot equity prices every holding through `GET /api/v3/ticker/price`.

@details The fake once served no `ticker/price` route, so every journey that
read the Spot account logged "could not price BTC via BTCUSDT ticker" and
reported the equity as unavailable. These tests pin the route's path, its
payload and Binance's answer for a symbol it does not list.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest
from binance.client import Client
from binance.exceptions import BinanceAPIException
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_account_reader import (
    SpotAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_session_factory import (
    SpotSessionFactory,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
    IExchangeCredentialsProvider,
    ResolvedCredentials,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "tests" / "sanity"))
from binance_fake_server import run_binance_fake_server
from fake_exchange.server import FakeServerUrls


class _Credentials(IExchangeCredentialsProvider):
    def resolve(self) -> ResolvedCredentials:
        return ResolvedCredentials(
            ExchangeCredentials(api_key="fake-key", api_secret="fake-secret"),
            CredentialsSource.FILE,
        )

    def save_to_file(self, api_key: str, api_secret: str) -> None:
        raise AssertionError("not used by this test")


@contextmanager
def _fake_exchange() -> Iterator[FakeServerUrls]:
    with (
        run_binance_fake_server() as urls,
        patch.object(Client, "API_TESTNET_URL", urls.spot),
    ):
        yield urls


def test_the_spot_equity_prices_every_holding_at_its_last_price(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with _fake_exchange() as urls, caplog.at_level(logging.WARNING):
        status = SpotAccountReader(
            SpotSessionFactory(), _Credentials()
        ).check_connection()

    # The fake's opening account: 100,000 USDT, 10 BTC at 50,000 and
    # 100 ETH at 3,000.
    assert status.equity == Decimal(100_000 + 10 * 50_000 + 100 * 3_000)
    assert ("GET", "/api/v3/ticker/price") in urls.requests
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


def test_the_price_follows_the_last_price_and_a_bad_symbol_is_1121() -> None:
    with _fake_exchange() as urls:
        client = Client(api_key="k", api_secret="s", testnet=True)
        price = client.get_symbol_ticker(symbol="ETHUSDT")
        with pytest.raises(BinanceAPIException) as raised:
            client.get_symbol_ticker(symbol="NOPEUSDT")

    assert price == {"symbol": "ETHUSDT", "price": "3000.00000000"}
    assert raised.value.code == -1121
    assert ("GET", "/api/v3/ticker/price") in urls.requests
