from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from binance.enums import HistoricalKlinesType
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.infrastructure.binance.client import (
    PythonBinanceClient,
)


@pytest.fixture
def client():
    # EPIC-021A: PythonBinanceClient no longer constructs the SDK client
    # itself (ExchangeSessionFactory is the one place allowed to) — inject a
    # mock session directly instead of patching Client() construction.
    mock_instance = Mock()

    # Fake Binance API response in the documented twelve-column order.
    mock_instance.get_historical_klines_generator.return_value = [
        [
            1672531200000,
            "16500.0",
            "16600.0",
            "16400.0",
            "16550.0",
            "100.5",
            1672534799999,
            "1660000.0",
            5000,
            "50.0",
            "825000.0",
            "0",
        ]
    ]

    yield PythonBinanceClient(client=mock_instance)


def test_get_historical_klines_parsing(client):
    start_time = datetime(2023, 1, 1, tzinfo=UTC)

    klines = client.get_historical_klines("BTCUSDT", TimeFrame.ONE_HOUR, start_time)

    assert len(klines) == 1
    kline = klines[0]

    assert kline.symbol == "BTCUSDT"
    assert kline.interval == "1h"

    # 1672531200000 ms = 2023-01-01 00:00:00 UTC
    assert kline.open_time == datetime(2023, 1, 1, 0, 0, 0, tzinfo=UTC)
    assert kline.close_time == datetime(2023, 1, 1, 0, 59, 59, 999000, tzinfo=UTC)

    assert kline.open_price == 16500.0
    assert kline.high_price == 16600.0
    assert kline.low_price == 16400.0
    assert kline.close_price == 16550.0

    assert kline.volume == 100.5
    assert kline.quote_asset_volume == 1660000.0
    assert kline.number_of_trades == 5000
    assert kline.taker_buy_base_asset_volume == 50.0
    assert kline.taker_buy_quote_asset_volume == 825000.0


def test_get_historical_klines_arguments(client):
    # Test that datetime is correctly formatted to string before passing to underlying lib
    start_time = datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC)

    client.get_historical_klines("ETHUSDT", TimeFrame.ONE_MINUTE, start_time)

    # Check what the mocked underlying client received
    underlying_mock = client.client
    underlying_mock.get_historical_klines_generator.assert_called_once_with(
        "ETHUSDT",
        "1m",
        "01 Jan 2023 12:00:00",
        None,
        klines_type=HistoricalKlinesType.SPOT,
    )
