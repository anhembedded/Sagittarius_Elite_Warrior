from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.application.ports.i_market_data_repository import (
    DatabaseStatusSnapshot,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.get_database_gaps import (
    GetDatabaseGapsQuery,
    GetDatabaseGapsQueryHandler,
)
from Sagittarius_Elite_Warrior.src.domain.models.data_gap import DataGap
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame


def test_get_database_gaps_empty_database():
    repo = Mock()
    repo.get_database_status.return_value = DatabaseStatusSnapshot(
        first_record=None, last_record=None, total_candles=0, gaps=0
    )
    handler = GetDatabaseGapsQueryHandler(repo)

    result = handler.execute(
        GetDatabaseGapsQuery(symbol="BTCUSDT", interval=TimeFrame.ONE_MINUTE)
    )

    assert result.total_gaps == 0
    assert result.total_missing_candles == 0
    assert result.coverage_percentage == 0.0
    assert len(result.gaps) == 0


def test_get_database_gaps_with_detected_gaps():
    repo = Mock()
    t0 = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
    t1 = datetime(2024, 1, 1, 10, 0, tzinfo=UTC)
    t2 = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
    t3 = datetime(2024, 1, 1, 20, 0, tzinfo=UTC)

    repo.get_database_status.return_value = DatabaseStatusSnapshot(
        first_record=t0, last_record=t3, total_candles=1000, gaps=1
    )
    repo.get_gaps.return_value = [
        DataGap(
            symbol="BTCUSDT",
            interval=TimeFrame.ONE_MINUTE,
            start_time=t1,
            end_time=t2,
            missing_candles=120,
        )
    ]
    handler = GetDatabaseGapsQueryHandler(repo)

    result = handler.execute(
        GetDatabaseGapsQuery(symbol="BTCUSDT", interval=TimeFrame.ONE_MINUTE)
    )

    assert result.total_gaps == 1
    assert result.total_missing_candles == 120
    assert len(result.gaps) == 1
    assert result.gaps[0].duration_text == "2.0h"
    assert result.gaps[0].missing_candles == 120
    assert len(result.coverage_segments) >= 2


def test_get_database_gaps_invalid_symbol_or_interval_raises():
    repo = Mock()
    handler = GetDatabaseGapsQueryHandler(repo)

    with pytest.raises(ValueError, match="Symbol cannot be empty"):
        handler.execute(
            GetDatabaseGapsQuery(symbol="", interval=TimeFrame.ONE_MINUTE)
        )

    with pytest.raises(ValueError):
        TimeFrame("999x")
