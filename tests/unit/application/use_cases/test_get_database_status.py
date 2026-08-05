import pytest
from unittest.mock import Mock
from Binace_Bot.src.application.use_cases.queries.get_database_status.query import GetDatabaseStatusQuery
from Binace_Bot.src.application.use_cases.queries.get_database_status.handler import GetDatabaseStatusQueryHandler
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame

@pytest.fixture
def mock_repo():
    return Mock()

@pytest.fixture
def handler(mock_repo):
    return GetDatabaseStatusQueryHandler(mock_repo)

def test_get_database_status_success(handler, mock_repo):
    mock_repo.get_database_status.return_value = {
        "first_record": "2023-01-01",
        "last_record": "2023-01-02",
        "total_candles": 100,
        "gaps": 0
    }

    query = GetDatabaseStatusQuery(symbol="BTCUSDT", interval="1m")
    result = handler.execute(query)

    assert result["total_candles"] == 100
    assert result["gaps"] == 0
    mock_repo.get_database_status.assert_called_once_with(symbol="BTCUSDT", interval=TimeFrame.ONE_MINUTE)

def test_get_database_status_invalid_interval(handler, mock_repo):
    query = GetDatabaseStatusQuery(symbol="BTCUSDT", interval="invalid")
    
    with pytest.raises(ValueError, match="Invalid interval: invalid"):
        handler.execute(query)
    
    mock_repo.get_database_status.assert_not_called()
