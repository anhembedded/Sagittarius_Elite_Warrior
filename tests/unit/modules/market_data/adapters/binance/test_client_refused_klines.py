"""`BUG-172` — a refusal that retrying cannot change is a named, readable error.

@details Futures has no `1s` klines (`-1120`) and each testnet lists fewer
symbols than the mainnet (`-1121`). `PythonBinanceClient` turns exactly those two
answers of the SDK into `ExchangeRefusedKlinesError`; any other API error is left
as it is, and the transient-network retry is untouched.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from binance.exceptions import BinanceAPIException
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.binance.client import (
    PythonBinanceClient,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_exchange_client import (
    ExchangeRefusedKlinesError,
)


def _api_error(code: int, message: str) -> BinanceAPIException:
    response = Mock(status_code=400, text=f'{{"code": {code}, "msg": "{message}"}}')
    response.json.return_value = {"code": code, "msg": message}
    return BinanceAPIException(response, 400, response.text)


def _raising(error: Exception):
    """A kline generator that fails on its first page, as the SDK's does: the
    request is made lazily, when the generator is first iterated."""
    raise error
    yield  # pragma: no cover - makes this a generator


def _client_raising(error: Exception) -> PythonBinanceClient:
    sdk = Mock()
    sdk.get_historical_klines_generator.side_effect = lambda *a, **k: _raising(error)
    return PythonBinanceClient(client=sdk)


def _stream(client: PythonBinanceClient, market: MarketType, interval: TimeFrame):
    return list(
        client.stream_historical_klines(
            market, "BTCUSDT", interval, "1 day ago UTC", None, None, None
        )
    )


def test_an_interval_the_market_has_none_of_is_a_readable_refusal() -> None:
    client = _client_raising(_api_error(-1120, "Invalid interval."))

    with pytest.raises(ExchangeRefusedKlinesError) as refused:
        _stream(client, MarketType.FUTURES_USD_M, TimeFrame.ONE_SECOND)

    assert refused.value.reason == (
        "This exchange has no 1s candles for its USDⓈ-M Futures market."
    )
    assert isinstance(refused.value.__cause__, BinanceAPIException)


def test_a_symbol_the_exchange_does_not_list_is_a_readable_refusal() -> None:
    client = _client_raising(_api_error(-1121, "Invalid symbol."))

    with pytest.raises(ExchangeRefusedKlinesError) as refused:
        _stream(client, MarketType.SPOT, TimeFrame.ONE_MINUTE)

    assert refused.value.reason == (
        "This exchange does not list BTCUSDT on its Spot market."
    )


def test_a_refusal_is_not_retried() -> None:
    client = _client_raising(_api_error(-1120, "Invalid"))

    with pytest.raises(ExchangeRefusedKlinesError):
        _stream(client, MarketType.FUTURES_USD_M, TimeFrame.ONE_SECOND)

    assert client.client.get_historical_klines_generator.call_count == 1


def test_any_other_api_error_is_left_as_it_is() -> None:
    other = _api_error(-1003, "Too many requests.")
    client = _client_raising(other)

    with pytest.raises(BinanceAPIException) as raised:
        _stream(client, MarketType.SPOT, TimeFrame.ONE_MINUTE)

    assert raised.value is other
