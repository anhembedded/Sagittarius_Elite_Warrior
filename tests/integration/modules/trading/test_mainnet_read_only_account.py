"""`EPIC-034E` — the read-only mainnet account against the fake Binance server.

The real adapters run, python-binance included: only the base URLs move (the
spot and wallet families) and the key comes from the environment variables the
owner will set. What the fake exchange answers is set by each test through its
`api_restrictions`, so a read-only key, a key that can trade and a key that can
withdraw each meet the same code. Not proven here, and not provable from this
sandbox (HTTP 451 to `*.binance.com`): the owner's real balances. That is the
owner's manual check, recorded in `EPIC-034E`.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
from binance.client import Client
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.mainnet.mainnet_read_session_factory import (
    MainnetReadSessionFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.mainnet.mainnet_readonly_account_reader import (
    MainnetReadOnlyAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.mainnet.mainnet_readonly_credentials import (
    MAINNET_READONLY_ENV_API_KEY,
    MAINNET_READONLY_ENV_API_SECRET,
    MainnetReadOnlyCredentials,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connect_failure import (
    ConnectFailure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_account_snapshot import (
    VenueAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.account_source import (
    AccountSource,
)
from Sagittarius_Elite_Warrior.tests.secret_stores import InMemorySecretStore

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "sanity"))
from binance_fake_server import FakeServerUrls, run_binance_fake_server

_PLACING = ("POST", "PUT", "DELETE")


@pytest.fixture
def exchange(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeServerUrls]:
    monkeypatch.setenv(MAINNET_READONLY_ENV_API_KEY, "mainnet-key")
    monkeypatch.setenv(MAINNET_READONLY_ENV_API_SECRET, "mainnet-secret")
    with (
        run_binance_fake_server() as urls,
        patch.object(Client, "API_URL", urls.spot),
        patch.object(Client, "MARGIN_API_URL", urls.margin),
    ):
        yield urls


def _reader() -> MainnetReadOnlyAccountReader:
    return MainnetReadOnlyAccountReader(
        MainnetReadOnlyCredentials(InMemorySecretStore()), MainnetReadSessionFactory()
    )


def test_a_read_only_key_shows_the_account_with_its_balances_fees_and_orders(
    exchange: FakeServerUrls,
) -> None:
    answer = _reader().read("BTCUSDT")

    assert isinstance(answer, VenueAccountSnapshot), answer
    assert answer.source is AccountSource.SPOT_MAINNET_READONLY
    assert AccountSource.SPOT_MAINNET_READONLY.venue_title == "Mainnet · read only"
    assert answer.available > 0
    assert {h.asset for h in answer.holdings} >= {"USDT", "BTC"}
    assert answer.commission.taker > 0
    assert answer.key_permissions is not None
    assert answer.key_permissions.is_read_only
    assert answer.open_order_count == 0
    assert answer.rules.symbol == "BTCUSDT"
    assert answer.price > 0


def test_a_key_that_can_trade_is_accepted_and_says_so(exchange: FakeServerUrls) -> None:
    exchange.api_restrictions.enable_spot_and_margin_trading = True

    answer = _reader().read("BTCUSDT")

    assert isinstance(answer, VenueAccountSnapshot), answer
    assert answer.key_permissions is not None
    assert answer.key_permissions.can_trade_spot
    assert not answer.key_permissions.is_read_only


def test_a_key_with_futures_on_is_accepted_but_not_called_read_only(
    exchange: FakeServerUrls,
) -> None:
    exchange.api_restrictions.enable_futures = True

    answer = _reader().read("BTCUSDT")

    assert isinstance(answer, VenueAccountSnapshot), answer
    assert answer.key_permissions is not None
    assert not answer.key_permissions.is_read_only
    assert answer.key_permissions.beyond_reading == ("trade Futures",)


def test_a_key_that_can_withdraw_is_refused_before_anything_else_is_read(
    exchange: FakeServerUrls,
) -> None:
    exchange.api_restrictions.enable_withdrawals = True
    exchange.requests.clear()

    answer = _reader().read("BTCUSDT")

    assert answer == ConnectFailure(
        AccountSource.SPOT_MAINNET_READONLY,
        ConnectionFailureKind.WITHDRAWAL_ENABLED,
        "withdrawals",
    )
    read_paths = {path for _, path in exchange.requests}
    assert "/sapi/v1/account/apiRestrictions" in read_paths
    assert "/api/v3/account" not in read_paths
    assert "/api/v3/openOrders" not in read_paths


def test_nothing_is_ever_placed_cancelled_or_tested(exchange: FakeServerUrls) -> None:
    exchange.requests.clear()

    _reader().read("BTCUSDT")
    exchange.api_restrictions.enable_spot_and_margin_trading = True
    _reader().read("BTCUSDT")

    assert exchange.requests, "the reader asked the exchange for nothing"
    assert not [
        (method, path)
        for method, path in exchange.requests
        if method in _PLACING or "order" in path.lower() and "openOrders" not in path
    ]


def test_without_the_variables_there_is_no_key_and_no_request(
    exchange: FakeServerUrls, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(MAINNET_READONLY_ENV_API_KEY)
    exchange.requests.clear()

    answer = _reader().read("BTCUSDT")

    assert answer == ConnectFailure(
        AccountSource.SPOT_MAINNET_READONLY, ConnectionFailureKind.NOT_CONFIGURED
    )
    assert exchange.requests == []


def test_a_testnet_key_is_never_read_as_the_mainnet_key(
    exchange: FakeServerUrls, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(MAINNET_READONLY_ENV_API_KEY)
    monkeypatch.delenv(MAINNET_READONLY_ENV_API_SECRET)
    monkeypatch.setenv("BINANCE_SPOT_TESTNET_API_KEY", "testnet-key")
    monkeypatch.setenv("BINANCE_SPOT_TESTNET_API_SECRET", "testnet-secret")
    monkeypatch.setenv("BINANCE_FUTURES_TESTNET_API_KEY", "testnet-key")
    monkeypatch.setenv("BINANCE_FUTURES_TESTNET_API_SECRET", "testnet-secret")

    assert (
        MainnetReadOnlyCredentials(InMemorySecretStore()).resolve().credentials is None
    )


def test_an_exchange_under_maintenance_is_named(exchange: FakeServerUrls) -> None:
    exchange.maintenance.on = True

    answer = _reader().read("BTCUSDT")

    assert isinstance(answer, ConnectFailure)
    assert answer.kind is ConnectionFailureKind.MAINTENANCE


def test_a_permissions_answer_without_the_withdrawal_flag_is_not_a_pass(
    exchange: FakeServerUrls, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        exchange.api_restrictions,
        "payload",
        lambda: {"enableReading": True, "enableSpotAndMarginTrading": False},
    )

    answer = _reader().read("BTCUSDT")

    assert isinstance(answer, ConnectFailure)
    assert answer.kind is ConnectionFailureKind.NETWORK
    assert answer.detail == "the key's permissions"
