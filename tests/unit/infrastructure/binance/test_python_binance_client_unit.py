from datetime import UTC, datetime
from unittest.mock import Mock, patch

import pytest
from Sagittarius_Elite_Warrior.src.application.ports.i_exchange_client import (
    ExchangeRequestCancelled,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.infrastructure.binance.client import (
    _KLINE_STREAM_CHUNK_SIZE,
    PythonBinanceClient,
)


def _raw_kline(index: int) -> list:
    return [
        1672531200000 + index * 60_000,
        "100.0",
        "110.0",
        "90.0",
        "105.0",
        "1000.0",
        1672531259999 + index * 60_000,
        "105000.0",
        50,
        "500.0",
        "52500.0",
        "0",
    ]


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


def test_historical_kline_iteration_stops_cooperatively_when_cancelled():
    injected_client = Mock()
    injected_client.get_historical_klines_generator.return_value = [
        [
            1672531200000 + index * 60_000,
            "100.0",
            "110.0",
            "90.0",
            "105.0",
            "1000.0",
            1672531259999 + index * 60_000,
            "105000.0",
            50,
            "500.0",
            "52500.0",
            "0",
        ]
        for index in range(10)
    ]
    cancellation_checks = 0

    def cancellation_requested() -> bool:
        nonlocal cancellation_checks
        cancellation_checks += 1
        return cancellation_checks >= 4

    client = PythonBinanceClient(client=injected_client)

    with pytest.raises(ExchangeRequestCancelled):
        client.get_historical_klines(
            "BTCUSDT",
            TimeFrame.ONE_MINUTE,
            datetime(2023, 1, 1, tzinfo=UTC),
            cancellation_requested=cancellation_requested,
        )

    assert cancellation_checks == 4


def test_stream_historical_klines_yields_bounded_chunks_instead_of_one_giant_list():
    """BUG-025 regression test: the whole point of streaming is that no
    single chunk grows past the page size, regardless of how many klines
    the underlying generator produces in total — proving RAM usage per
    chunk is bounded, not proportional to the requested range."""
    total_raw_klines = _KLINE_STREAM_CHUNK_SIZE * 2 + 5
    injected_client = Mock()
    injected_client.get_historical_klines_generator.return_value = (
        _raw_kline(i) for i in range(total_raw_klines)
    )

    client = PythonBinanceClient(client=injected_client)

    chunks = list(
        client.stream_historical_klines(
            "BTCUSDT", TimeFrame.ONE_MINUTE, datetime(2023, 1, 1, tzinfo=UTC)
        )
    )

    assert [len(c) for c in chunks] == [
        _KLINE_STREAM_CHUNK_SIZE,
        _KLINE_STREAM_CHUNK_SIZE,
        5,
    ]
    assert sum(len(c) for c in chunks) == total_raw_klines
    assert all(kline.symbol == "BTCUSDT" for chunk in chunks for kline in chunk)


def test_stream_historical_klines_reports_progress_and_maps_fields_correctly():
    injected_client = Mock()
    injected_client.get_historical_klines_generator.return_value = [_raw_kline(0)]
    progress_calls: list[int] = []

    client = PythonBinanceClient(client=injected_client)

    chunks = list(
        client.stream_historical_klines(
            "BTCUSDT",
            TimeFrame.ONE_MINUTE,
            datetime(2023, 1, 1, tzinfo=UTC),
            progress_callback=progress_calls.append,
        )
    )

    assert len(chunks) == 1
    assert progress_calls == [1]
    assert chunks[0][0].symbol == "BTCUSDT"
    assert chunks[0][0].open_price == 100.0


def test_stream_historical_klines_stops_cooperatively_when_cancelled():
    injected_client = Mock()
    injected_client.get_historical_klines_generator.return_value = (
        _raw_kline(i) for i in range(10)
    )
    cancellation_checks = 0

    def cancellation_requested() -> bool:
        nonlocal cancellation_checks
        cancellation_checks += 1
        return cancellation_checks >= 4

    client = PythonBinanceClient(client=injected_client)

    with pytest.raises(ExchangeRequestCancelled):
        list(
            client.stream_historical_klines(
                "BTCUSDT",
                TimeFrame.ONE_MINUTE,
                datetime(2023, 1, 1, tzinfo=UTC),
                cancellation_requested=cancellation_requested,
            )
        )

    assert cancellation_checks == 4


def test_get_available_symbols_returns_only_trading_status_symbols_sorted():
    """BOT-102 — BREAK/HALT/other non-TRADING symbols must not appear in the
    picker; the exchange lists them but they cannot actually be backtested
    against fresh data."""
    injected_client = Mock()
    injected_client.get_exchange_info.return_value = {
        "symbols": [
            {"symbol": "ETHUSDT", "status": "TRADING"},
            {"symbol": "BTCUSDT", "status": "TRADING"},
            {"symbol": "DELISTEDUSDT", "status": "BREAK"},
        ]
    }

    client = PythonBinanceClient(client=injected_client)

    assert client.get_available_symbols() == ["BTCUSDT", "ETHUSDT"]


def test_get_available_symbols_returns_empty_list_when_exchange_info_is_empty():
    injected_client = Mock()
    injected_client.get_exchange_info.return_value = {"symbols": []}

    client = PythonBinanceClient(client=injected_client)

    assert client.get_available_symbols() == []
