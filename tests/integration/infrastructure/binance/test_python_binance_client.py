from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.infrastructure.binance.client import (
    PythonBinanceClient,
)


@pytest.fixture
def client():
    # Patch the actual binance Client so we don't make real HTTP requests during testing
    with patch(
        "Sagittarius_Elite_Warrior.src.infrastructure.binance.client.Client"
    ) as MockClient:
        # Mock instance of the Client
        mock_instance = MockClient.return_value

        # Fake Binance API response format
        # [
        #   [
        #     1499040000000,      // Kline open time
        #     "0.01634790",       // Open price
        #     "0.80000000",       // High price
        #     "0.01575800",       // Low price
        #     "0.01577100",       // Close price
        #     "148976.11427815",  // Volume
        #     1499644799999,      // Kline close time
        #     "2434.19055334",    // Quote asset volume
        #     308,                // Number of trades
        #     "1756.87402397",    // Taker buy base asset volume
        #     "28.46694368",      // Taker buy quote asset volume
        #     "0"                 // Unused field. Ignore.
        #   ]
        # ]
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

        yield PythonBinanceClient(api_key="", api_secret="")


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
        "ETHUSDT", "1m", "01 Jan 2023 12:00:00", None
    )
