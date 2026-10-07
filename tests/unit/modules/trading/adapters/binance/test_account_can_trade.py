"""`EPIC-034D` — both account readers report the account's own `canTrade` flag
as the exchange sent it, and `None` (never `True`) when it sent none."""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.account_can_trade import (
    can_trade_of,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_account_reader import (
    FuturesAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_account_reader import (
    SpotAccountReader,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
    ResolvedCredentials,
)


def _provider() -> Mock:
    provider = Mock()
    provider.resolve.return_value = ResolvedCredentials(
        ExchangeCredentials("key", "secret"), CredentialsSource.FILE
    )
    return provider


def _spot(account: dict) -> SpotAccountReader:
    client = Mock()
    client.ping.return_value = {}
    client.get_server_time.return_value = {"serverTime": 0}
    client.get_account.return_value = {
        "balances": [{"asset": "USDT", "free": "10", "locked": "0"}],
        **account,
    }
    client.get_symbol_ticker.return_value = {"price": "1"}
    factory = Mock()
    factory.create_account_client.return_value = client
    return SpotAccountReader(factory, _provider())


def _futures(account: dict) -> FuturesAccountReader:
    client = Mock()
    client.futures_ping.return_value = {}
    client.futures_time.return_value = {"serverTime": 0}
    client.futures_account.return_value = {
        "assets": [{"asset": "USDT", "walletBalance": "10"}],
        "positions": [],
        **account,
    }
    client.futures_get_position_mode.return_value = {"dualSidePosition": False}
    client.futures_get_multi_assets_mode.return_value = {"multiAssetsMargin": False}
    factory = Mock()
    factory.create_trading_client.return_value = client
    return FuturesAccountReader(factory, _provider())


@pytest.mark.parametrize("build", [_spot, _futures], ids=["spot", "futures"])
@pytest.mark.parametrize("flag", [True, False])
def test_the_flag_is_reported_as_the_exchange_sent_it(build, flag: bool) -> None:
    assert build({"canTrade": flag}).check_connection().can_trade is flag


@pytest.mark.parametrize("build", [_spot, _futures], ids=["spot", "futures"])
def test_an_account_without_the_flag_reports_unknown_not_true(build) -> None:
    assert build({}).check_connection().can_trade is None


@pytest.mark.parametrize("junk", ["true", 1, None])
def test_a_flag_that_is_not_a_boolean_is_unknown(junk: object) -> None:
    assert can_trade_of({"canTrade": junk}) is None
