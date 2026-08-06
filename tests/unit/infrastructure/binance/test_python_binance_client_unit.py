from unittest.mock import Mock, patch
from datetime import datetime, timezone
from Binace_Bot.src.infrastructure.binance.client import PythonBinanceClient
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame


@patch("Binace_Bot.src.infrastructure.binance.client.Client")
def test_python_binance_client_with_end_str(mock_client_class):
    mock_binance_client_instance = Mock()
    mock_client_class.return_value = mock_binance_client_instance

    # Simulate the generator returning one kline
    mock_kline = [
        1672531200000,
        "100.0",
        "110.0",
        "90.0",
        "105.0",
        "1000.0",
        1672531259999,
        "105000.0",
        50,
        "500.0",
        "52500.0",
        "0",
    ]
    mock_binance_client_instance.get_historical_klines_generator.return_value = [
        mock_kline
    ]

    client = PythonBinanceClient()

    start_dt = datetime(2023, 1, 1, tzinfo=timezone.utc)
    end_dt = datetime(2023, 1, 2, tzinfo=timezone.utc)

    klines = client.get_historical_klines(
        "BTCUSDT", TimeFrame.ONE_MINUTE, start_dt, end_dt
    )

    # Assert the generator was called with formatted strings
    mock_binance_client_instance.get_historical_klines_generator.assert_called_once_with(
        "BTCUSDT", "1m", "01 Jan 2023 00:00:00", "02 Jan 2023 00:00:00"
    )

    assert len(klines) == 1
    assert klines[0].symbol == "BTCUSDT"
    assert klines[0].open_price == 100.0


@patch("Binace_Bot.src.infrastructure.binance.client.Client")
def test_python_binance_client_without_end_str(mock_client_class):
    mock_binance_client_instance = Mock()
    mock_client_class.return_value = mock_binance_client_instance
    mock_binance_client_instance.get_historical_klines_generator.return_value = []

    client = PythonBinanceClient()
    start_dt = datetime(2023, 1, 1, tzinfo=timezone.utc)

    client.get_historical_klines("ETHUSDT", TimeFrame.ONE_HOUR, start_dt)

    # end_str defaults to None
    mock_binance_client_instance.get_historical_klines_generator.assert_called_once_with(
        "ETHUSDT", "1h", "01 Jan 2023 00:00:00", None
    )
