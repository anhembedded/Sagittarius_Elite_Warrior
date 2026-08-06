import pytest
from unittest.mock import Mock
from datetime import datetime, timezone

from Binace_Bot.src.application.use_cases.queries.scan_all_databases.query import (
    DatabaseStatusDTO,
    ScanAllDatabasesQuery,
)
from Binace_Bot.src.application.use_cases.queries.scan_all_databases.handler import (
    ScanAllDatabasesQueryHandler,
)
from Binace_Bot.src.application.ports.i_market_data_repository import (
    DatabaseStatusSnapshot,
)


@pytest.fixture
def mock_repo():
    return Mock()


@pytest.fixture
def handler(mock_repo):
    return ScanAllDatabasesQueryHandler(mock_repo)


def test_returns_dto_list_for_non_empty_databases(handler, mock_repo):
    """Handler returns one DatabaseStatusDTO per non-empty symbol/interval pair."""
    mock_repo.get_database_status.return_value = DatabaseStatusSnapshot(
        first_record=datetime(2024, 1, 1, tzinfo=timezone.utc),
        last_record=datetime(2024, 6, 1, tzinfo=timezone.utc),
        total_candles=500,
        gaps=0,
    )

    query = ScanAllDatabasesQuery(symbols=["BTCUSDT"], intervals=["1h"])
    results = handler.execute(query)

    assert len(results) == 1
    dto = results[0]
    assert isinstance(dto, DatabaseStatusDTO)
    assert dto.symbol == "BTCUSDT"
    assert dto.interval == "1h"
    assert dto.total_candles == "500"
    assert dto.gaps == "0"
    assert dto.status_text == "OK"


def test_skips_empty_databases(handler, mock_repo):
    """Entries with total_candles == 0 are silently skipped."""
    mock_repo.get_database_status.return_value = DatabaseStatusSnapshot(
        first_record=None,
        last_record=None,
        total_candles=0,
        gaps=0,
    )

    query = ScanAllDatabasesQuery(symbols=["BTCUSDT", "ETHUSDT"], intervals=["1m"])
    results = handler.execute(query)

    assert results == []
    # Repository was still queried for each pair
    assert mock_repo.get_database_status.call_count == 2


def test_gap_detected_sets_correct_status_text(handler, mock_repo):
    """When gaps > 0, status_text should contain the gap count."""
    mock_repo.get_database_status.return_value = DatabaseStatusSnapshot(
        first_record=datetime(2024, 1, 1, tzinfo=timezone.utc),
        last_record=datetime(2024, 6, 1, tzinfo=timezone.utc),
        total_candles=1000,
        gaps=3,
    )

    query = ScanAllDatabasesQuery(symbols=["BTCUSDT"], intervals=["1m"])
    results = handler.execute(query)

    assert len(results) == 1
    assert results[0].status_text == "3 gaps found!"
    assert results[0].gaps == "3"


def test_iterates_all_symbol_interval_combinations(handler, mock_repo):
    """Handler iterates the full cartesian product of symbols × intervals."""
    mock_repo.get_database_status.return_value = DatabaseStatusSnapshot(
        first_record=None,
        last_record=None,
        total_candles=100,
        gaps=0,
    )

    query = ScanAllDatabasesQuery(
        symbols=["BTCUSDT", "ETHUSDT"],
        intervals=["1m", "1h"],
    )
    results = handler.execute(query)

    # 2 symbols × 2 intervals = 4 pairs, all non-empty
    assert len(results) == 4
    assert mock_repo.get_database_status.call_count == 4

    returned_pairs = {(dto.symbol, dto.interval) for dto in results}
    assert returned_pairs == {
        ("BTCUSDT", "1m"),
        ("BTCUSDT", "1h"),
        ("ETHUSDT", "1m"),
        ("ETHUSDT", "1h"),
    }


def test_invalid_interval_is_skipped_gracefully(handler, mock_repo):
    """Invalid interval strings are skipped without raising an exception."""
    query = ScanAllDatabasesQuery(symbols=["BTCUSDT"], intervals=["invalid_interval"])
    results = handler.execute(query)

    assert results == []
    mock_repo.get_database_status.assert_not_called()


def test_repository_exception_is_caught_per_pair(handler, mock_repo):
    """A repository error on one pair does not abort the whole scan."""
    mock_repo.get_database_status.side_effect = [
        Exception("DB connection failed"),
        DatabaseStatusSnapshot(
            first_record=None, last_record=None, total_candles=200, gaps=0
        ),
    ]

    query = ScanAllDatabasesQuery(symbols=["BTCUSDT", "ETHUSDT"], intervals=["1h"])
    results = handler.execute(query)

    # First pair failed (skipped), second succeeded
    assert len(results) == 1
    assert results[0].symbol == "ETHUSDT"


def test_dto_is_frozen(handler, mock_repo):
    """DatabaseStatusDTO must be immutable (frozen=True)."""
    mock_repo.get_database_status.return_value = DatabaseStatusSnapshot(
        first_record=None, last_record=None, total_candles=50, gaps=0
    )

    query = ScanAllDatabasesQuery(symbols=["BTCUSDT"], intervals=["1m"])
    results = handler.execute(query)
    dto = results[0]

    with pytest.raises(Exception):  # FrozenInstanceError
        dto.symbol = "ETHUSDT"  # type: ignore[misc]
