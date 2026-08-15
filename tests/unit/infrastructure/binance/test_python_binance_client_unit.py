from datetime import UTC, datetime
from unittest.mock import Mock, patch

from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.infrastructure.binance.client import (
    PythonBinanceClient,
)


def test_injected_client_is_used_directly_without_patching_the_sdk():
    """
    DIP: a pre-built client can be injected via __init__, so tests (and callers) don't
    need unittest.mock.patch reaching into the binance.client.Client construction.
    """
    injected_client = Mock()
    injected_client.get_historical_klines_generator.return_value = []

    client = PythonBinanceClient(client=injected_client)

    assert client.client is injected_client

    client.get_historical_klines(
        "BTCUSDT", TimeFrame.ONE_MINUTE, datetime(2023, 1, 1, tzinfo=UTC)
    )
    injected_client.get_historical_klines_generator.assert_called_once()


@patch("Sagittarius_Elite_Warrior.src.infrastructure.binance.client.Client")
def test_no_injected_client_falls_back_to_constructing_the_real_sdk_client(
    mock_client_class,
):
    """When no client is injected, the real Client(api_key, api_secret) is built — the
    existing default behavior every current call site (container wiring) relies on."""
    PythonBinanceClient(api_key="k", api_secret="s")
    mock_client_class.assert_called_once_with("k", "s")


def test_get_historical_klines_propagates_underlying_client_errors():
    """Errors from the injected client must not be swallowed."""
    injected_client = Mock()
    injected_client.get_historical_klines_generator.side_effect = RuntimeError(
        "API rate limit"
    )

    client = PythonBinanceClient(client=injected_client)

    try:
        client.get_historical_klines(
            "BTCUSDT", TimeFrame.ONE_MINUTE, datetime(2023, 1, 1, tzinfo=UTC)
        )
        raise AssertionError("Expected RuntimeError to propagate")
    except RuntimeError as exc:
        assert "API rate limit" in str(exc)


@patch("Sagittarius_Elite_Warrior.src.infrastructure.binance.client.Client")
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

    start_dt = datetime(2023, 1, 1, tzinfo=UTC)
    end_dt = datetime(2023, 1, 2, tzinfo=UTC)

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


@patch("Sagittarius_Elite_Warrior.src.infrastructure.binance.client.Client")
def test_python_binance_client_without_end_str(mock_client_class):
    mock_binance_client_instance = Mock()
    mock_client_class.return_value = mock_binance_client_instance
    mock_binance_client_instance.get_historical_klines_generator.return_value = []

    client = PythonBinanceClient()
    start_dt = datetime(2023, 1, 1, tzinfo=UTC)

    client.get_historical_klines("ETHUSDT", TimeFrame.ONE_HOUR, start_dt)

    # end_str defaults to None
    mock_binance_client_instance.get_historical_klines_generator.assert_called_once_with(
        "ETHUSDT", "1h", "01 Jan 2023 00:00:00", None
    )
