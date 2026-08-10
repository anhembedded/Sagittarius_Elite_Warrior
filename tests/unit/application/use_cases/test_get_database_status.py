from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
from Binace_Bot.src.application.ports.i_market_data_repository import (
    DatabaseStatusSnapshot,
)
from Binace_Bot.src.application.use_cases.queries.get_database_status.handler import (
    GetDatabaseStatusQueryHandler,
)
from Binace_Bot.src.application.use_cases.queries.get_database_status.query import (
    GetDatabaseStatusQuery,
)
from Binace_Bot.src.application.use_cases.queries.scan_all_databases.query import (
    DatabaseStatusDTO,
)
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame


@pytest.fixture
def mock_repo():
    return Mock()


@pytest.fixture
def handler(mock_repo):
    return GetDatabaseStatusQueryHandler(mock_repo)


def test_get_database_status_success(handler, mock_repo):
    """Handler returns a typed DatabaseStatusDTO — consistent with ScanAllDatabasesQueryHandler."""
    mock_repo.get_database_status.return_value = DatabaseStatusSnapshot(
        first_record=datetime(2023, 1, 1, tzinfo=timezone.utc),
        last_record=datetime(2023, 1, 2, tzinfo=timezone.utc),
        total_candles=100,
        gaps=0,
    )

    query = GetDatabaseStatusQuery(symbol="BTCUSDT", interval="1m")
    result = handler.execute(query)

    assert isinstance(result, DatabaseStatusDTO)
    assert result.symbol == "BTCUSDT"
    assert result.interval == "1m"
    assert result.total_candles == "100"
    assert result.gaps == "0"
    assert result.status_text == "OK"
    mock_repo.get_database_status.assert_called_once_with(
        symbol="BTCUSDT", interval=TimeFrame.ONE_MINUTE
    )


def test_get_database_status_with_gaps(handler, mock_repo):
    """status_text reflects the gap count, matching ScanAllDatabasesQueryHandler's format."""
    mock_repo.get_database_status.return_value = DatabaseStatusSnapshot(
        first_record=None,
        last_record=None,
        total_candles=50,
        gaps=4,
    )

    query = GetDatabaseStatusQuery(symbol="ETHUSDT", interval="5m")
    result = handler.execute(query)

    assert result.status_text == "4 gaps found!"
    assert result.first_record == "N/A"
    assert result.last_record == "N/A"


def test_get_database_status_invalid_interval(handler, mock_repo):
    query = GetDatabaseStatusQuery(symbol="BTCUSDT", interval="invalid")

    with pytest.raises(ValueError, match="Invalid interval: invalid"):
        handler.execute(query)

    mock_repo.get_database_status.assert_not_called()


def test_get_database_status_invalid_symbol(handler, mock_repo):
    query = GetDatabaseStatusQuery(symbol="", interval="1m")

    with pytest.raises(ValueError, match="Invalid symbol"):
        handler.execute(query)

    mock_repo.get_database_status.assert_not_called()
