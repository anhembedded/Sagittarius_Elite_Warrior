from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.get_historical_klines.handler import (
    GetHistoricalKlinesQueryHandler,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.get_historical_klines.query import (
    GetHistoricalKlinesQuery,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame


def test_get_historical_klines_handler_success():
    # Arrange
    repo_mock = Mock()
    repo_mock.get_klines.return_value = ["mock_kline_1", "mock_kline_2"]

    handler = GetHistoricalKlinesQueryHandler(repo_mock)

    start_dt = datetime(2023, 1, 1, tzinfo=UTC)
    query = GetHistoricalKlinesQuery(
        symbol="BTCUSDT",
        interval="1h",
        start_time=start_dt,
        limit=100,
        order_by_desc=True,
    )

    # Act
    result = handler.execute(query)

    # Assert
    assert result == ["mock_kline_1", "mock_kline_2"]
    repo_mock.get_klines.assert_called_once_with(
        symbol="BTCUSDT",
        interval=TimeFrame.ONE_HOUR,
        start_time=start_dt,
        end_time=None,
        limit=100,
        order_by_desc=True,
    )


def test_get_historical_klines_handler_invalid_interval():
    repo_mock = Mock()
    handler = GetHistoricalKlinesQueryHandler(repo_mock)

    query = GetHistoricalKlinesQuery(symbol="BTCUSDT", interval="invalid_interval")

    with pytest.raises(ValueError, match="Invalid interval: invalid_interval"):
        handler.execute(query)


def test_get_historical_klines_handler_batch_success():
    # Arrange
    repo_mock = Mock()

    # Return different lists based on symbol to verify correct mapping
    def mock_get_klines(*args, **kwargs):
        symbol = kwargs.get("symbol")
        if symbol == "BTCUSDT":
            return ["btc_1", "btc_2"]
        elif symbol == "ETHUSDT":
            return ["eth_1", "eth_2"]
        return []

    repo_mock.get_klines.side_effect = mock_get_klines

    handler = GetHistoricalKlinesQueryHandler(repo_mock)

    query = GetHistoricalKlinesQuery(
        symbol=["BTCUSDT", "ETHUSDT"],
        interval="1h",
        limit=50,
    )

    # Act
    result = handler.execute(query)

    # Assert
    assert isinstance(result, dict)
    assert result == {"BTCUSDT": ["btc_1", "btc_2"], "ETHUSDT": ["eth_1", "eth_2"]}

    # Assert repository was called for each symbol
    assert repo_mock.get_klines.call_count == 2
