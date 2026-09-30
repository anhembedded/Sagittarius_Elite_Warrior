"""`EPIC-028E` — what `FuturesHistoryReader` and `SpotHistoryReader` do
around the exchange: which symbols count as active, and how a failed read is
reported.

@details The session factories and the credentials provider are small
subclasses of their ports; only the raw SDK client, which is third-party, is a
`Mock`. The request shapes and the window splitting against a real HTTP round
trip are `tests/integration/infrastructure/binance/
test_history_readers_against_fake_server.py`'s.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from unittest.mock import Mock

import pytest
from binance.exceptions import BinanceAPIException
from requests.exceptions import ConnectionError as RequestsConnectionError
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_history_reader import (
    FuturesHistoryReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_history_reader import (
    SpotHistoryReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_history_unavailable_error import (
    AccountHistoryUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    SymbolOrderMetadata,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_market_metadata_provider import (
    FakeMarketMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
    IExchangeCredentialsProvider,
    ResolvedCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_spot_session_factory import (
    ISpotSessionClient,
    ISpotSessionFactory,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_trading_session_factory import (
    ITradingSessionClient,
    ITradingSessionFactory,
)

_NOW = datetime(2026, 9, 30, tzinfo=UTC)


class _Credentials(IExchangeCredentialsProvider):
    def __init__(self, configured: bool = True) -> None:
        self._credentials = (
            ExchangeCredentials(api_key="key", api_secret="secret")
            if configured
            else None
        )

    def resolve(self) -> ResolvedCredentials:
        return ResolvedCredentials(self._credentials, CredentialsSource.FILE)

    def save_to_file(self, api_key: str, api_secret: str) -> None:
        raise AssertionError("not used")


class _FuturesSessions(ITradingSessionFactory):
    def __init__(self, client: Any) -> None:
        self._client = client

    def create_trading_client(
        self, credentials: ExchangeCredentials
    ) -> ITradingSessionClient:
        return self._client


class _SpotSessions(ISpotSessionFactory):
    def __init__(self, client: Any) -> None:
        self._client = client

    def create_account_client(
        self, credentials: ExchangeCredentials
    ) -> ISpotSessionClient:
        return self._client

    def create_trading_client(
        self, credentials: ExchangeCredentials
    ) -> ISpotSessionClient:
        raise AssertionError("history reads use the account client")


def _listed(symbol: str) -> SymbolOrderMetadata:
    return SymbolOrderMetadata(
        symbol=symbol,
        status="TRADING",
        step_size=Decimal("0.00001"),
        tick_size=Decimal("0.01"),
        min_notional=Decimal(5),
        quantity_precision=None,
        price_precision=None,
        fetched_at=_NOW,
    )


def _api_error() -> BinanceAPIException:
    exc = BinanceAPIException.__new__(BinanceAPIException)
    exc.code = -1121
    exc.message = "Invalid symbol."
    exc.status_code = 400
    exc.response = None
    exc.request = None
    return exc


def _futures(client: Any, configured: bool = True) -> FuturesHistoryReader:
    return FuturesHistoryReader(
        _FuturesSessions(client), _Credentials(configured), lambda: _NOW
    )


def _spot(client: Any, *listed: str) -> SpotHistoryReader:
    return SpotHistoryReader(
        _SpotSessions(client),
        _Credentials(),
        FakeMarketMetadataProvider(_listed(symbol) for symbol in listed),
        lambda: _NOW,
    )


def test_futures_active_symbols_are_open_positions_and_open_orders() -> None:
    client = Mock()
    client.futures_position_information.return_value = [
        {"symbol": "ETHUSDT", "positionAmt": "0.5"},
        {"symbol": "XRPUSDT", "positionAmt": "0"},
        {"symbol": "BTCUSDT", "positionAmt": "-0.01"},
    ]
    client.futures_get_open_orders.return_value = [{"symbol": "SOLUSDT"}]

    assert _futures(client).active_symbols() == ("BTCUSDT", "ETHUSDT", "SOLUSDT")


def test_spot_active_symbols_are_listed_pairs_of_held_assets_and_open_orders() -> None:
    """`DOGE` is held but its pair is not listed; `ETH` is zero; `USDT` is the
    quote asset itself."""
    client = Mock()
    client.get_account.return_value = {
        "balances": [
            {"asset": "BTC", "free": "0.1", "locked": "0"},
            {"asset": "ETH", "free": "0", "locked": "0"},
            {"asset": "BNB", "free": "0", "locked": "2"},
            {"asset": "DOGE", "free": "5", "locked": "0"},
            {"asset": "USDT", "free": "100", "locked": "0"},
        ]
    }
    client.get_open_orders.return_value = [{"symbol": "SOLUSDT"}]

    reader = _spot(client, "BTCUSDT", "BNBUSDT", "ETHUSDT", "SOLUSDT")

    assert reader.active_symbols() == ("BNBUSDT", "BTCUSDT", "SOLUSDT")


def test_a_read_asks_from_since_up_to_the_clock() -> None:
    client = Mock()
    client.futures_get_all_orders.return_value = []

    _futures(client).order_history("BTCUSDT", _NOW - timedelta(hours=1))

    kwargs = client.futures_get_all_orders.call_args.kwargs
    assert kwargs["symbol"] == "BTCUSDT"
    assert kwargs["endTime"] == int(_NOW.timestamp() * 1000)
    assert kwargs["startTime"] == int(_NOW.timestamp() * 1000) - 3_600_000


@pytest.mark.parametrize("failure", [_api_error(), RequestsConnectionError("reset")])
def test_a_failed_futures_read_raises_the_readers_own_error(
    failure: Exception,
) -> None:
    client = Mock()
    client.futures_account_trades.side_effect = failure

    with pytest.raises(AccountHistoryUnavailableError) as raised:
        _futures(client).trade_history("BTCUSDT", _NOW - timedelta(days=1))

    assert raised.value.__cause__ is failure


def test_a_failed_spot_read_raises_the_readers_own_error() -> None:
    client = Mock()
    client.get_my_trades.side_effect = _api_error()

    with pytest.raises(AccountHistoryUnavailableError):
        _spot(client).trade_history("BTCUSDT", _NOW - timedelta(hours=2))


def test_no_credentials_raises_before_any_request() -> None:
    client = Mock()

    with pytest.raises(AccountHistoryUnavailableError):
        _futures(client, configured=False).order_history("BTCUSDT", _NOW)

    client.futures_get_all_orders.assert_not_called()
