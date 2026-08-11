from datetime import datetime, timezone
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

    start_dt = datetime(2023, 1, 1, tzinfo=timezone.utc)
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
