import dataclasses
from threading import Event
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.application.ports.i_market_data_repository import (
    DatabaseStatusSnapshot,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.scan_all_databases.handler import (
    ScanAllDatabasesQueryHandler,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.scan_all_databases.query import (
    DatabaseStatusDTO,
    ScanAllDatabasesQuery,
)

_EMPTY_SNAPSHOT = DatabaseStatusSnapshot(
    first_record=None, last_record=None, total_candles=0, gaps=0
)


@pytest.fixture
def mock_repo():
    return Mock()


@pytest.fixture
def handler(mock_repo):
    return ScanAllDatabasesQueryHandler(mock_repo)


def test_returns_dto_list_for_non_empty_databases(handler, mock_repo):
    """Handler returns one DatabaseStatusDTO per non-empty symbol/interval pair."""
    mock_repo.get_database_status_for_intervals.return_value = {
        "1h": DatabaseStatusSnapshot(
            first_record="2024-01-01",
            last_record="2024-06-01",
            total_candles=500,
            gaps=0,
        )
    }

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
    mock_repo.get_database_status_for_intervals.return_value = {"1m": _EMPTY_SNAPSHOT}

    query = ScanAllDatabasesQuery(symbols=["BTCUSDT", "ETHUSDT"], intervals=["1m"])
    results = handler.execute(query)

    assert results == []
    # Repository was still queried once per symbol
    assert mock_repo.get_database_status_for_intervals.call_count == 2


def test_gap_detected_sets_correct_status_text(handler, mock_repo):
    """When gaps > 0, status_text should contain the gap count."""
    mock_repo.get_database_status_for_intervals.return_value = {
        "1m": DatabaseStatusSnapshot(
            first_record="2024-01-01",
            last_record="2024-06-01",
            total_candles=1000,
            gaps=3,
        )
    }

    query = ScanAllDatabasesQuery(symbols=["BTCUSDT"], intervals=["1m"])
    results = handler.execute(query)

    assert len(results) == 1
    assert results[0].status_text == "3 gaps found!"
    assert results[0].gaps == "3"


def test_one_repository_call_per_symbol_not_per_pair(handler, mock_repo):
    """BUG-078: a symbol's intervals must be fetched over ONE call (one shard
    session), not one call per (symbol, interval) pair — the whole point of the
    redesign that replaced the 8100-connection boot-time scan."""
    snapshot = DatabaseStatusSnapshot(
        first_record=None, last_record=None, total_candles=100, gaps=0
    )
    mock_repo.get_database_status_for_intervals.return_value = {
        "1m": snapshot,
        "1h": snapshot,
    }

    query = ScanAllDatabasesQuery(
        symbols=["BTCUSDT", "ETHUSDT"],
        intervals=["1m", "1h"],
    )
    results = handler.execute(query)

    # 2 symbols × 2 intervals = 4 non-empty entries...
    assert len(results) == 4
    # ...from exactly 2 repository calls (one per symbol), not 4.
    assert mock_repo.get_database_status_for_intervals.call_count == 2

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
    mock_repo.get_database_status_for_intervals.assert_not_called()


def test_repository_exception_is_caught_per_symbol(handler, mock_repo):
    """A repository error on one symbol does not abort the whole scan."""
    mock_repo.get_database_status_for_intervals.side_effect = [
        Exception("DB connection failed"),
        {
            "1h": DatabaseStatusSnapshot(
                first_record=None, last_record=None, total_candles=200, gaps=0
            )
        },
    ]

    query = ScanAllDatabasesQuery(symbols=["BTCUSDT", "ETHUSDT"], intervals=["1h"])
    results = handler.execute(query)

    # First symbol failed (skipped), second succeeded
    assert len(results) == 1
    assert results[0].symbol == "ETHUSDT"


def test_dto_is_frozen(handler, mock_repo):
    """DatabaseStatusDTO must be immutable (frozen=True)."""
    mock_repo.get_database_status_for_intervals.return_value = {
        "1m": DatabaseStatusSnapshot(
            first_record=None, last_record=None, total_candles=50, gaps=0
        )
    }

    query = ScanAllDatabasesQuery(symbols=["BTCUSDT"], intervals=["1m"])
    results = handler.execute(query)
    dto = results[0]

    with pytest.raises(dataclasses.FrozenInstanceError):
        dto.symbol = "ETHUSDT"  # type: ignore[misc]


def test_cancelled_query_does_not_start_repository_scan(handler, mock_repo):
    """BUG-041: shutdown cancellation must prevent queued database work."""
    cancellation = Event()
    cancellation.set()
    query = ScanAllDatabasesQuery(
        symbols=["BTCUSDT", "ETHUSDT"],
        intervals=["1m", "1h"],
        cancellation_requested=cancellation.is_set,
    )

    results = handler.execute(query)

    assert results == []
    mock_repo.get_database_status_for_intervals.assert_not_called()


def test_cancellation_stops_symbols_queued_after_an_inflight_scan(handler, mock_repo):
    """BUG-041: a cancellation raised mid-scan must skip the remaining symbols."""
    cancellation = Event()
    symbols = [f"SYMBOL_{index}" for index in range(100)]
    snapshot = DatabaseStatusSnapshot(
        first_record=None,
        last_record=None,
        total_candles=1,
        gaps=0,
    )

    def cancel_during_first_scan(*_args, **_kwargs):
        cancellation.set()
        return {"1m": snapshot}

    mock_repo.get_database_status_for_intervals.side_effect = cancel_during_first_scan
    query = ScanAllDatabasesQuery(
        symbols=symbols,
        intervals=["1m"],
        cancellation_requested=cancellation.is_set,
    )

    handler.execute(query)

    assert 1 <= mock_repo.get_database_status_for_intervals.call_count < len(symbols)
